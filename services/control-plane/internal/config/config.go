package config

import (
	"os"
	"sync"
)

// Config represents the application configuration
type Config struct {
	Port                string
	DatabaseURL         string
	JWTSecret           string
	Environment         string
	OrchestratorType    string
	DockerSocketPath    string
	KubeconfigPath      string
	KubernetesNamespace string
	OllamaBaseURL       string
	NATSURL             string
	ServiceID           string
}

var (
	instance *Config
	once     sync.Once
)

// Get returns the singleton Config instance
func Get() *Config {
	once.Do(func() {
		instance = &Config{
			Port:                getEnv("PORT", "8080"),
			DatabaseURL:         getEnv("DATABASE_URL", "postgres://agentic:agentic@localhost:5433/agentic?sslmode=disable"),
			JWTSecret:           getEnv("JWT_SECRET", "dev-secret-change-in-production"),
			Environment:         getEnv("ENVIRONMENT", "development"),
			OrchestratorType:    getEnv("ORCHESTRATOR_TYPE", "docker-bind"),
			DockerSocketPath:    getEnv("DOCKER_SOCKET_PATH", "/var/run/docker.sock"),
			KubeconfigPath:      getEnv("KUBECONFIG_PATH", ""),
			KubernetesNamespace: getEnv("KUBERNETES_NAMESPACE", "default"),
			OllamaBaseURL:       getEnv("OLLAMA_BASE_URL", "http://localhost:11434"),
			NATSURL:             getEnv("NATS_URL", "nats://localhost:4222"),
			ServiceID:           getEnv("SERVICE_ID", "control-plane"),
		}
	})
	return instance
}

// Load is deprecated; use Get() instead for singleton pattern
func Load() *Config {
	return Get()
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
