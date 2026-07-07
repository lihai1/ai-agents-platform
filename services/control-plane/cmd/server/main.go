package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
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

	// Initialize repositories
	userRepo := repository.NewUserRepository(database)
	orgRepo := repository.NewOrganizationRepository(database)
	projectRepo := repository.NewProjectRepository(database)
	repoRepo := repository.NewRepositoryRepository(database)
	chatContainerRepo := repository.NewChatContainerRepository(database)

	// Initialize orchestrator
	containerOrchestrator, err := orchestrator.NewOrchestrator(orchestrator.OrchestratorTypeDocker)
	if err != nil {
		log.Fatalf("Failed to create orchestrator: %v", err)
	}
	containerManager := orchestrator.NewManager(containerOrchestrator)

	// Initialize services
	authService := service.NewAuthService(cfg.JWTSecret, userRepo)
	projectService := service.NewProjectService(projectRepo, orgRepo, userRepo)
	repositoryService := service.NewRepositoryService(repoRepo, projectRepo)
	chatContainerService := service.NewChatContainerService(chatContainerRepo, repoRepo, containerManager)

	// Initialize handlers
	authHandler := handlers.NewAuthHandler(authService)
	projectHandler := handlers.NewProjectHandler(projectService)
	repositoryHandler := handlers.NewRepositoryHandler(repositoryService)
	// chatContainerHandler := handlers.NewChatContainerHandler(chatContainerService) // No longer needed with NATS
	healthHandler := handlers.NewHealthHandler()

	// Setup router
	r := mux.NewRouter()

	// Handle OPTIONS requests before any routing
	r.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			if req.Method == "OPTIONS" {
				w.Header().Set("Access-Control-Allow-Origin", "*")
				w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
				w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
				w.Header().Set("Access-Control-Max-Age", "86400")
				w.WriteHeader(http.StatusOK)
				return
			}
			next.ServeHTTP(w, req)
		})
	})

	// CORS middleware
	r.Use(middleware.CORSMiddleware)
	r.Use(middleware.LoggingMiddleware)

	// Health endpoints
	r.HandleFunc("/healthz", healthHandler.Health).Methods("GET")
	r.HandleFunc("/readyz", healthHandler.Ready).Methods("GET")

	// API routes
	api := r.PathPrefix("/api/v1").Subrouter()
	api.Use(middleware.AuthMiddleware(cfg.JWTSecret))

	// Auth routes (no auth required)
	r.HandleFunc("/api/v1/auth/login", authHandler.Login).Methods("POST")
	r.HandleFunc("/api/v1/auth/register", authHandler.Register).Methods("POST")

	// Project routes
	api.HandleFunc("/projects", projectHandler.ListProjects).Methods("GET", "OPTIONS")
	api.HandleFunc("/projects", projectHandler.CreateProject).Methods("POST", "OPTIONS")
	api.HandleFunc("/projects/{id}", projectHandler.GetProject).Methods("GET", "OPTIONS")
	api.HandleFunc("/projects/{id}", projectHandler.UpdateProject).Methods("PUT", "OPTIONS")
	api.HandleFunc("/projects/{id}", projectHandler.DeleteProject).Methods("DELETE", "OPTIONS")

	// Repository routes
	api.HandleFunc("/repositories", repositoryHandler.ListRepositories).Methods("GET", "OPTIONS")
	api.HandleFunc("/repositories", repositoryHandler.CreateRepository).Methods("POST", "OPTIONS")
	api.HandleFunc("/repositories/{id}", repositoryHandler.GetRepository).Methods("GET", "OPTIONS")
	api.HandleFunc("/repositories/{id}", repositoryHandler.UpdateRepository).Methods("PUT", "OPTIONS")
	api.HandleFunc("/repositories/{id}", repositoryHandler.DeleteRepository).Methods("DELETE", "OPTIONS")

	// Chat container routes (removed - now using NATS)
	// api.HandleFunc("/containers", chatContainerHandler.CreateContainer).Methods("POST")
	// api.HandleFunc("/containers", chatContainerHandler.ListContainers).Methods("GET")
	// api.HandleFunc("/containers/{chat_id}", chatContainerHandler.GetContainer).Methods("GET")
	// api.HandleFunc("/containers/{chat_id}/stop", chatContainerHandler.StopContainer).Methods("POST")
	// api.HandleFunc("/containers/{chat_id}", chatContainerHandler.RemoveContainer).Methods("DELETE")

	// Initialize NATS client
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = "nats://localhost:4222"
	}

	nc, err := nats.Connect(natsURL)
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}
	defer nc.Close()

	// Subscribe to chat start messages
	_, err = nc.Subscribe("chat.start", func(msg *nats.Msg) {
		handleChatStart(msg, chatContainerService, nc)
	})
	if err != nil {
		log.Fatalf("Failed to subscribe to chat.start: %v", err)
	}

	// Subscribe to chat close messages
	_, err = nc.Subscribe("chat.close", func(msg *nats.Msg) {
		handleChatClose(msg, chatContainerService)
	})
	if err != nil {
		log.Fatalf("Failed to subscribe to chat.close: %v", err)
	}

	log.Println("Subscribed to NATS chat.start and chat.close subjects")

	// Wrap router with CORS handler that handles OPTIONS at server level
	handler := http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		// Set CORS headers for all requests
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("Access-Control-Max-Age", "86400")

		// Handle OPTIONS requests immediately for CORS preflight
		if req.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		r.ServeHTTP(w, req)
	})

	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      handler,
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

	// Graceful shutdown
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

// ChatStartMessage represents a chat start message from NATS
type ChatStartMessage struct {
	MessageID     string `json:"message_id"`
	ChatID        string `json:"chat_id"`
	RepositoryID  string `json:"repository_id"`
	ProjectID     string `json:"project_id"`
	MockMode      bool   `json:"mock_mode"`
	Timestamp     string `json:"timestamp"`
	SchemaVersion string `json:"schema_version"`
}

// ChatCloseMessage represents a chat close message from NATS
type ChatCloseMessage struct {
	MessageID     string `json:"message_id"`
	ChatID        string `json:"chat_id"`
	Timestamp     string `json:"timestamp"`
	SchemaVersion string `json:"schema_version"`
}

func handleChatStart(msg *nats.Msg, chatContainerService *service.ChatContainerService, nc *nats.Conn) {
	var chatMsg ChatStartMessage
	if err := json.Unmarshal(msg.Data, &chatMsg); err != nil {
		log.Printf("[NATS RECEIVE] Failed to unmarshal chat start message: %v", err)
		return
	}

	log.Printf("[NATS RECEIVE] Received chat start message on subject: %s", msg.Subject)
	log.Printf("[NATS RECEIVE] Chat start payload: %s", string(msg.Data))
	log.Printf("[NATS RECEIVE] Chat ID: %s, Repository ID: %s, Mock Mode: %v", chatMsg.ChatID, chatMsg.RepositoryID, chatMsg.MockMode)

	// Create container for the chat
	_, err := chatContainerService.CreateContainer(chatMsg.ChatID, chatMsg.RepositoryID, chatMsg.MockMode)
	if err != nil {
		log.Printf("[NATS RECEIVE] Failed to create container for chat %s: %v", chatMsg.ChatID, err)
		return
	}

	log.Printf("[NATS RECEIVE] Successfully created container for chat %s", chatMsg.ChatID)

	// Publish agent.chat.{chat_id}.start message to signal container is ready
	agentStartMsg := map[string]interface{}{
		"message_id":     chatMsg.MessageID,
		"chat_id":        chatMsg.ChatID,
		"repository_id":  chatMsg.RepositoryID,
		"project_id":     chatMsg.ProjectID,
		"mock_mode":      chatMsg.MockMode,
		"timestamp":      chatMsg.Timestamp,
		"schema_version": chatMsg.SchemaVersion,
	}
	agentStartData, _ := json.Marshal(agentStartMsg)
	subject := fmt.Sprintf("agent.chat.%s.start", chatMsg.ChatID)

	log.Printf("[NATS PUBLISH] Publishing agent start message to subject: %s", subject)
	log.Printf("[NATS PUBLISH] Agent start payload: %s", string(agentStartData))

	if err := nc.Publish(subject, agentStartData); err != nil {
		log.Printf("[NATS PUBLISH] Failed to publish agent start message: %v", err)
		return
	}

	log.Printf("[NATS PUBLISH] Successfully published agent start message for chat %s", chatMsg.ChatID)
}

func handleChatClose(msg *nats.Msg, chatContainerService *service.ChatContainerService) {
	var chatMsg ChatCloseMessage
	if err := json.Unmarshal(msg.Data, &chatMsg); err != nil {
		log.Printf("[NATS RECEIVE] Failed to unmarshal chat close message: %v", err)
		return
	}

	log.Printf("[NATS RECEIVE] Received chat close message on subject: %s", msg.Subject)
	log.Printf("[NATS RECEIVE] Chat close payload: %s", string(msg.Data))
	log.Printf("[NATS RECEIVE] Chat ID: %s", chatMsg.ChatID)

	// Stop and remove container for the chat
	if err := chatContainerService.StopContainer(chatMsg.ChatID); err != nil {
		log.Printf("[NATS RECEIVE] Failed to stop container for chat %s: %v", chatMsg.ChatID, err)
	}

	if err := chatContainerService.RemoveContainer(chatMsg.ChatID); err != nil {
		log.Printf("[NATS RECEIVE] Failed to remove container for chat %s: %v", chatMsg.ChatID, err)
		return
	}

	log.Printf("[NATS RECEIVE] Successfully terminated container for chat %s", chatMsg.ChatID)
}
