package orchestrator

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/google/uuid"
)

// Manager manages container lifecycle for runs
type Manager struct {
	orchestrator ContainerOrchestrator
}

// NewManager creates a new container manager
func NewManager(orchestrator ContainerOrchestrator) *Manager {
	return &Manager{
		orchestrator: orchestrator,
	}
}

// CreateChatContainer creates a new container for a run
func (m *Manager) CreateChatContainer(runID, repositoryURL, branch string, credentials *RepositoryCredentials, mockMode bool) (*ChatContainerInfo, error) {
	containerName := fmt.Sprintf("automated-run-%s", runID)
	config := ContainerConfig{
		RunID:         runID,
		RepositoryURL: repositoryURL,
		Branch:        branch,
		Credentials:   credentials,
		Image:         "agentic-agent-worker:latest",
		ContainerName: containerName,
		Network:       "agentic-network",
		EnvVars: map[string]string{
			"RUN_ID":         runID,
			"REPOSITORY_URL": repositoryURL,
			"BRANCH":         branch,
			"NATS_URL":       "nats://nats:4222",
			"MOCK_MODE":      "false",
		},
	}

	if mockMode {
		config.EnvVars["MOCK_MODE"] = "true"
	}

	if credentials != nil {
		config.EnvVars["GIT_USERNAME"] = credentials.Username
		config.EnvVars["GIT_TOKEN"] = credentials.Token
	}

	// Pass through environment variables required by the worker
	for _, key := range []string{
		"DATABASE_URL",
		"OPENAI_API_KEY",
		"ANTHROPIC_API_KEY",
		"OLLAMA_BASE_URL",
		"LANGSMITH_API_KEY",
		"LANGSMITH_PROJECT",
		"LLM_PROVIDER",
	} {
		if value := os.Getenv(key); value != "" {
			config.EnvVars[key] = value
		}
	}

	result, err := m.orchestrator.CreateContainer(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create container: %w", err)
	}

	return &ChatContainerInfo{
		ID:            uuid.New().String(),
		RunID:         runID,
		ContainerID:   result.ContainerID,
		ContainerName: containerName,
		RepositoryURL: repositoryURL,
		Branch:        branch,
		Status:        result.Status,
		CreatedAt:     time.Now(),
	}, nil
}

// StopChatContainer stops a chat container
func (m *Manager) StopChatContainer(containerID string) error {
	if strings.HasPrefix(containerID, "mock-") {
		return nil
	}
	if err := m.orchestrator.StopContainer(containerID); err != nil {
		return fmt.Errorf("failed to stop container: %w", err)
	}
	return nil
}

// RemoveChatContainer removes a chat container
func (m *Manager) RemoveChatContainer(containerID string) error {
	if strings.HasPrefix(containerID, "mock-") {
		return nil
	}
	if err := m.orchestrator.RemoveContainer(containerID); err != nil {
		return fmt.Errorf("failed to remove container: %w", err)
	}
	return nil
}

// GetChatContainerStatus gets the status of a chat container
func (m *Manager) GetChatContainerStatus(containerID string) (*ChatContainerStatus, error) {
	status, err := m.orchestrator.GetContainerStatus(containerID)
	if err != nil {
		return nil, fmt.Errorf("failed to get container status: %w", err)
	}

	return &ChatContainerStatus{
		ContainerID: status.ContainerID,
		Status:      status.Status,
		Running:     status.Running,
	}, nil
}

// StartWorker starts a worker container for a run
func (m *Manager) StartWorker(runID, repositoryURL, branch string, credentials *RepositoryCredentials, mockMode bool) (*ChatContainerInfo, error) {
	return m.CreateChatContainer(runID, repositoryURL, branch, credentials, mockMode)
}

// CreateSingleAgentContainer creates a new container for a single-agent worker
// TODO: Make agent type configurable via request parameters or configuration
// Currently hardcoded to use the single-agent Docker image
func (m *Manager) CreateSingleAgentContainer(runID, repositoryURL, branch string, credentials *RepositoryCredentials, mockMode bool) (*ChatContainerInfo, error) {
	containerName := fmt.Sprintf("single-agent-run-%s", runID)
	config := ContainerConfig{
		RunID:         runID,
		RepositoryURL: repositoryURL,
		Branch:        branch,
		Credentials:   credentials,
		// TODO: Make image name configurable via environment variable or config file
		// Currently hardcoded to single-agent image
		Image:         "agentic-single-agent-worker:latest",
		ContainerName: containerName,
		Network:       "control-plane_default",
		EnvVars: map[string]string{
			"RUN_ID":         runID,
			"REPOSITORY_URL": repositoryURL,
			"BRANCH":         branch,
			"NATS_URL":       "nats://agentic-nats:4222",
			"MOCK_MODE":      "false",
			// TODO: Make agent type configurable - currently hardcoded
			"AGENT_TYPE": "single-agent",
		},
	}

	if mockMode {
		config.EnvVars["MOCK_MODE"] = "true"
	}

	if credentials != nil {
		config.EnvVars["GIT_USERNAME"] = credentials.Username
		config.EnvVars["GIT_TOKEN"] = credentials.Token
	}

	// Pass through environment variables required by the worker
	for _, key := range []string{
		"DATABASE_URL",
		"OPENAI_API_KEY",
		"ANTHROPIC_API_KEY",
		"OLLAMA_BASE_URL",
		"LANGSMITH_API_KEY",
		"LANGSMITH_PROJECT",
		"LLM_PROVIDER",
	} {
		if value := os.Getenv(key); value != "" {
			config.EnvVars[key] = value
		}
	}

	result, err := m.orchestrator.CreateContainer(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create single-agent container: %w", err)
	}

	return &ChatContainerInfo{
		ID:            uuid.New().String(),
		RunID:         runID,
		ContainerID:   result.ContainerID,
		ContainerName: containerName,
		RepositoryURL: repositoryURL,
		Branch:        branch,
		Status:        result.Status,
		CreatedAt:     time.Now(),
	}, nil
}

// StopWorker stops and removes a worker container for a run
func (m *Manager) StopWorker(containerID string) error {
	// Stop the container
	if err := m.StopChatContainer(containerID); err != nil {
		return fmt.Errorf("failed to stop worker container: %w", err)
	}

	// Remove the container
	if err := m.RemoveChatContainer(containerID); err != nil {
		return fmt.Errorf("failed to remove worker container: %w", err)
	}

	return nil
}

// ChatContainerInfo holds information about a run container
type ChatContainerInfo struct {
	ID            string
	RunID         string
	ContainerID   string
	ContainerName string
	RepositoryURL string
	Branch        string
	Status        string
	CreatedAt     time.Time
}

// ChatContainerStatus holds the status of a chat container
type ChatContainerStatus struct {
	ContainerID string
	Status      string
	Running     bool
}
