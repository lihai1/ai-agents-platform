package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/agentic-engineering/control-plane/internal/config"
	"github.com/agentic-engineering/control-plane/internal/db"
	"github.com/agentic-engineering/control-plane/internal/handlers"
	"github.com/agentic-engineering/control-plane/internal/middleware"
	"github.com/agentic-engineering/control-plane/internal/orchestrator"
	"github.com/agentic-engineering/control-plane/internal/repository"
	"github.com/agentic-engineering/control-plane/internal/service"
	"github.com/gorilla/mux"
	"github.com/nats-io/nats.go"
)

func main() {
	cfg := config.Load()

	database, err := db.Connect(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer database.Close()

	initializeDatabase(database, cfg)

	userRepo := repository.NewUserRepository(database)
	orgRepo := repository.NewOrganizationRepository(database)
	projectRepo := repository.NewProjectRepository(database)
	repoRepo := repository.NewRepositoryRepository(database)
	chatContainerRepo := repository.NewChatContainerRepository(database)

	containerManager := initializeOrchestrator(cfg)
	cleanupOrphanedContainers(chatContainerRepo, containerManager)

	chatContainerService := service.NewChatContainerService(chatContainerRepo, repoRepo, containerManager)
	r := setupRouter(cfg, userRepo, orgRepo, projectRepo, repoRepo, chatContainerService)

	nc := setupNATS(cfg, chatContainerService, containerManager, repoRepo)
	defer nc.Close()

	startServer(cfg, r)
}

func initializeDatabase(database *sql.DB, cfg *config.Config) {
	log.Println("Running database migrations...")
	migrateCmd := exec.Command("migrate", "-path", "./migrations", "-database", cfg.DatabaseURL, "up")
	migrateCmd.Stdout = os.Stdout
	migrateCmd.Stderr = os.Stderr
	if err := migrateCmd.Run(); err != nil {
		log.Printf("Migration failed (may already be applied): %v", err)
	} else {
		log.Println("Migrations completed successfully")
	}

	if cfg.DefaultUserEmail != "" && cfg.DefaultUserPassword != "" {
		log.Println("Checking for default user...")
		userRepo := repository.NewUserRepository(database)
		existingUser, err := userRepo.GetByEmail(cfg.DefaultUserEmail)
		if err == nil && existingUser != nil {
			log.Printf("Default user already exists: %s", cfg.DefaultUserEmail)
			return
		}

		log.Printf("Creating default user: %s", cfg.DefaultUserEmail)
		defaultName := cfg.DefaultUserName
		if defaultName == "" {
			defaultName = "Default User"
		}
		authService := service.NewAuthService(cfg.JWTSecret, userRepo)
		_, err = authService.Register(cfg.DefaultUserEmail, cfg.DefaultUserPassword, defaultName)
		if err != nil {
			log.Printf("Failed to create default user: %v", err)
		} else {
			log.Printf("Default user created successfully: %s", cfg.DefaultUserEmail)
		}
	}
}

func initializeOrchestrator(cfg *config.Config) *orchestrator.Manager {
	containerOrchestrator, err := orchestrator.NewOrchestrator(
		orchestrator.OrchestratorType(cfg.OrchestratorType),
		cfg.DockerSocketPath,
		cfg.KubeconfigPath,
		cfg.KubernetesNamespace,
	)
	if err != nil {
		log.Fatalf("Failed to create orchestrator: %v", err)
	}
	containerManager := orchestrator.NewManager(containerOrchestrator)

	log.Printf("Initialized orchestrator: type=%s, docker_socket=%s, kubernetes_namespace=%s",
		cfg.OrchestratorType, cfg.DockerSocketPath, cfg.KubernetesNamespace)

	return containerManager
}

func cleanupOrphanedContainers(chatContainerRepo *repository.ChatContainerRepository, containerManager *orchestrator.Manager) {
	log.Println("INFO: Starting orphaned container cleanup on startup...")
	validRunIDs, err := chatContainerRepo.GetAllRunIDs()
	if err != nil {
		log.Printf("WARN: Failed to get valid run IDs from database, skipping container cleanup: %v", err)
		return
	}

	log.Printf("INFO: Found %d valid run IDs in database", len(validRunIDs))
	if err := containerManager.CleanupRogueContainers(validRunIDs); err != nil {
		log.Printf("WARN: Container cleanup encountered errors (startup will continue): %v", err)
	}
	log.Println("INFO: Container cleanup completed")
}

func setupRouter(cfg *config.Config, userRepo *repository.UserRepository, orgRepo *repository.OrganizationRepository, projectRepo *repository.ProjectRepository, repoRepo *repository.RepositoryRepository, chatContainerService *service.ChatContainerService) *mux.Router {
	authService := service.NewAuthService(cfg.JWTSecret, userRepo)
	projectService := service.NewProjectService(projectRepo, orgRepo, userRepo)
	repositoryService := service.NewRepositoryService(repoRepo, projectRepo)

	authHandler := handlers.NewAuthHandler(authService)
	projectHandler := handlers.NewProjectHandler(projectService)
	repositoryHandler := handlers.NewRepositoryHandler(repositoryService)
	healthHandler := handlers.NewHealthHandler()
	ollamaHandler := handlers.NewOllamaHandler(cfg.OllamaBaseURL)

	r := mux.NewRouter()
	r.Use(middleware.CORSMiddleware)
	r.Use(middleware.LoggingMiddleware)

	r.HandleFunc("/healthz", healthHandler.Health).Methods("GET")
	r.HandleFunc("/readyz", healthHandler.Ready).Methods("GET")

	api := r.PathPrefix("/api/v1").Subrouter()
	api.Use(middleware.AuthMiddleware(cfg.JWTSecret))

	r.HandleFunc("/api/v1/auth/login", authHandler.Login).Methods("POST")
	r.HandleFunc("/api/v1/auth/register", authHandler.Register).Methods("POST")
	r.HandleFunc("/api/v1/auth/me", authHandler.GetCurrentUser).Methods("GET")
	r.HandleFunc("/api/v1/ollama/models", ollamaHandler.ListModels).Methods("GET", "OPTIONS")

	api.HandleFunc("/projects", projectHandler.ListProjects).Methods("GET", "OPTIONS")
	api.HandleFunc("/projects", projectHandler.CreateProject).Methods("POST", "OPTIONS")
	api.HandleFunc("/projects/{id}", projectHandler.GetProject).Methods("GET", "OPTIONS")
	api.HandleFunc("/projects/{id}", projectHandler.UpdateProject).Methods("PUT", "OPTIONS")
	api.HandleFunc("/projects/{id}", projectHandler.DeleteProject).Methods("DELETE", "OPTIONS")

	api.HandleFunc("/repositories", repositoryHandler.ListRepositories).Methods("GET", "OPTIONS")
	api.HandleFunc("/repositories", repositoryHandler.CreateRepository).Methods("POST", "OPTIONS")
	api.HandleFunc("/repositories/{id}", repositoryHandler.GetRepository).Methods("GET", "OPTIONS")
	api.HandleFunc("/repositories/{id}", repositoryHandler.UpdateRepository).Methods("PUT", "OPTIONS")
	api.HandleFunc("/repositories/{id}", repositoryHandler.DeleteRepository).Methods("DELETE", "OPTIONS")

	return r
}

func setupNATS(cfg *config.Config, chatContainerService *service.ChatContainerService, containerManager *orchestrator.Manager, repoRepo *repository.RepositoryRepository) *nats.Conn {
	nc, err := nats.Connect(cfg.NATSURL)
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	js, err := nc.JetStream()
	if err != nil {
		log.Fatalf("Failed to initialize JetStream: %v", err)
	}

	handlers.CleanNATSMessageBus(js)

	_, err = nc.Subscribe("agent.control.>", func(msg *nats.Msg) {
		if strings.HasSuffix(msg.Subject, ".start") {
			handlers.HandleChatStart(msg, chatContainerService, containerManager, repoRepo, nc, js)
		} else if strings.HasSuffix(msg.Subject, ".close") {
			handlers.HandleChatClose(msg, chatContainerService, containerManager)
		} else if strings.HasSuffix(msg.Subject, ".resume") {
			handlers.HandleChatResume(msg, chatContainerService, containerManager, repoRepo, nc, js)
		}
	})
	if err != nil {
		log.Fatalf("Failed to subscribe to agent.control.>: %v", err)
	}

	log.Println("Subscribed to NATS agent.control.> (start/close/resume) subjects")

	return nc
}

func startServer(cfg *config.Config, r *mux.Router) {
	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		log.Printf("Server starting on port %s", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server exited")
}
