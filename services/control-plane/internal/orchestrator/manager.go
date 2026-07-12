package orchestrator

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/google/uuid"
)

// RepositoryConfig holds repository-related configuration
type RepositoryConfig struct {
	RunID         string
	RepositoryURL string
	Branch        string
	RepositoryID  string
	Credentials   *RepositoryCredentials
}

// LLMConfig holds LLM-related configuration
type LLMConfig struct {
	MockMode    bool
	LLMProvider string
	ModelName   string
	APIKey      string
}

// WorkerContainerConfig holds container deployment configuration
type WorkerContainerConfig struct {
	ImageName           string
	ContainerNamePrefix string
	Network             string
	NATSURL             string
	AgentType           string
}

// RunParameters holds run-specific parameters
type RunParameters struct {
	UserID          string
	ProjectID       string
	RepositoryID    string
	Task            string
	ChatkitThreadID string
	MaxTokens       int
	MaxCost         float64
	MaxRepairCount  int
}

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
func (m *Manager) StartWorker(repoConfig RepositoryConfig, llmConfig LLMConfig) (*ChatContainerInfo, error) {
	return m.CreateSpecialistAgentContainer(repoConfig, llmConfig)
}

// createContainerWithConfig is a helper method that creates a container with the given configuration
func (m *Manager) createContainerWithConfig(repoConfig RepositoryConfig, llmConfig LLMConfig, containerConfig WorkerContainerConfig) (*ChatContainerInfo, error) {
	containerName := fmt.Sprintf("%s-%s", containerConfig.ContainerNamePrefix, repoConfig.RunID)
	config := ContainerConfig{
		RunID:         repoConfig.RunID,
		RepositoryURL: repoConfig.RepositoryURL,
		Branch:        repoConfig.Branch,
		Credentials:   repoConfig.Credentials,
		Image:         containerConfig.ImageName,
		ContainerName: containerName,
		Network:       containerConfig.Network,
		EnvVars: map[string]string{
			"RUN_ID":           repoConfig.RunID,
			"REPOSITORY_URL":   repoConfig.RepositoryURL,
			"BRANCH":           repoConfig.Branch,
			"NATS_URL":         containerConfig.NATSURL,
			"MOCK_MODE":        os.Getenv("MOCK_MODE"),
			"LLM_PROVIDER":     llmConfig.LLMProvider,
			"MODEL_NAME":       llmConfig.ModelName,
			"API_KEY":          llmConfig.APIKey,
			"USER_ID":          "",  // Will be set from chat message
			"PROJECT_ID":       "",  // Will be set from chat message
			"REPOSITORY_ID":    "",  // Will be set from chat message
			"TASK":             "",  // Will be set from chat message
			"MAX_TOKENS":       "",  // Will be set from chat message
			"MAX_COST":         "",  // Will be set from chat message
			"MAX_REPAIR_COUNT": "2", // Default value
		},
	}

	if containerConfig.AgentType != "" {
		config.EnvVars["AGENT_TYPE"] = containerConfig.AgentType
	}

	// Set MOCK_MODE from environment variable with default "false"
	mockModeEnv := os.Getenv("MOCK_MODE")
	if mockModeEnv == "" {
		mockModeEnv = "false"
	}
	config.EnvVars["MOCK_MODE"] = mockModeEnv

	// Override with parameter if explicitly set to true
	if llmConfig.MockMode {
		config.EnvVars["MOCK_MODE"] = "true"
	}

	if repoConfig.Credentials != nil {
		config.EnvVars["GIT_USERNAME"] = repoConfig.Credentials.Username
		config.EnvVars["GIT_TOKEN"] = repoConfig.Credentials.Token
	}

	// Pass through environment variables required by the worker
	for _, key := range []string{
		"DATABASE_URL",
		"OPENAI_API_KEY",
		"ANTHROPIC_API_KEY",
		"OLLAMA_BASE_URL",
		"LANGSMITH_API_KEY",
		"LANGSMITH_PROJECT",
	} {
		if val := os.Getenv(key); val != "" {
			config.EnvVars[key] = val
		}
	}

	result, err := m.orchestrator.CreateContainer(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create container: %w", err)
	}

	return &ChatContainerInfo{
		ID:            uuid.New().String(),
		RunID:         repoConfig.RunID,
		ContainerID:   result.ContainerID,
		ContainerName: containerName,
		RepositoryURL: repoConfig.RepositoryURL,
		Branch:        repoConfig.Branch,
		Status:        result.Status,
		CreatedAt:     time.Now(),
	}, nil
}

// createContainerWithConfigAndParams is a helper method that creates a container with the given configuration and run parameters
func (m *Manager) createContainerWithConfigAndParams(repoConfig RepositoryConfig, llmConfig LLMConfig, containerConfig WorkerContainerConfig, runParams RunParameters) (*ChatContainerInfo, error) {
	containerName := fmt.Sprintf("%s-%s", containerConfig.ContainerNamePrefix, repoConfig.RunID)
	config := ContainerConfig{
		RunID:         repoConfig.RunID,
		RepositoryURL: repoConfig.RepositoryURL,
		Branch:        repoConfig.Branch,
		Credentials:   repoConfig.Credentials,
		Image:         containerConfig.ImageName,
		ContainerName: containerName,
		Network:       containerConfig.Network,
		EnvVars: map[string]string{
			"RUN_ID":           repoConfig.RunID,
			"REPOSITORY_URL":   repoConfig.RepositoryURL,
			"BRANCH":           repoConfig.Branch,
			"NATS_URL":         containerConfig.NATSURL,
			"MOCK_MODE":        "false",
			"LLM_PROVIDER":     llmConfig.LLMProvider,
			"MODEL_NAME":       llmConfig.ModelName,
			"API_KEY":          llmConfig.APIKey,
			"USER_ID":          runParams.UserID,
			"PROJECT_ID":       runParams.ProjectID,
			"REPOSITORY_ID":    runParams.RepositoryID,
			"TASK":             runParams.Task,
			"MAX_TOKENS":       fmt.Sprintf("%d", runParams.MaxTokens),
			"MAX_COST":         fmt.Sprintf("%f", runParams.MaxCost),
			"MAX_REPAIR_COUNT": fmt.Sprintf("%d", runParams.MaxRepairCount),
		},
	}

	if containerConfig.AgentType != "" {
		config.EnvVars["AGENT_TYPE"] = containerConfig.AgentType
	}

	// Set MOCK_MODE from environment variable with default "false"
	mockModeEnv := os.Getenv("MOCK_MODE")
	if mockModeEnv == "" {
		mockModeEnv = "false"
	}
	config.EnvVars["MOCK_MODE"] = mockModeEnv

	// Override with parameter if explicitly set to true
	if llmConfig.MockMode {
		config.EnvVars["MOCK_MODE"] = "true"
	}

	if repoConfig.Credentials != nil {
		config.EnvVars["GIT_USERNAME"] = repoConfig.Credentials.Username
		config.EnvVars["GIT_TOKEN"] = repoConfig.Credentials.Token
	}

	// Pass through environment variables required by the worker
	for _, key := range []string{
		"DATABASE_URL",
		"OPENAI_API_KEY",
		"ANTHROPIC_API_KEY",
		"OLLAMA_BASE_URL",
		"LANGSMITH_API_KEY",
		"LANGSMITH_PROJECT",
	} {
		if val := os.Getenv(key); val != "" {
			config.EnvVars[key] = val
		}
	}

	result, err := m.orchestrator.CreateContainer(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create container: %w", err)
	}

	return &ChatContainerInfo{
		ID:            uuid.New().String(),
		ContainerID:   result.ContainerID,
		ContainerName: containerName,
		RepositoryURL: repoConfig.RepositoryURL,
		Branch:        repoConfig.Branch,
		Status:        result.Status,
		CreatedAt:     time.Now(),
	}, nil
}

// CreateSingleAgentContainer creates a new container for a single-agent worker
func (m *Manager) CreateSingleAgentContainer(repoConfig RepositoryConfig, llmConfig LLMConfig) (*ChatContainerInfo, error) {
	containerConfig := WorkerContainerConfig{
		ImageName:           "agentic-single-agent-worker:latest",
		ContainerNamePrefix: "automated-single-agent-run",
		Network:             "agentic-network",
		NATSURL:             "nats://nats:4222",
		AgentType:           "single-agent",
	}
	return m.createContainerWithConfig(repoConfig, llmConfig, containerConfig)
}

// CreateSpecialistAgentContainer creates a new container for a specialist agent (multi-agent) worker
func (m *Manager) CreateSpecialistAgentContainer(repoConfig RepositoryConfig, llmConfig LLMConfig) (*ChatContainerInfo, error) {
	containerConfig := WorkerContainerConfig{
		ImageName:           "agentic-specialist-agent-worker:latest",
		ContainerNamePrefix: "automated-specialists-run",
		Network:             "agentic-network",
		NATSURL:             "nats://nats:4222",
		AgentType:           "specialist",
	}
	return m.createContainerWithConfig(repoConfig, llmConfig, containerConfig)
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

// CreateSingleAgentContainerWithParams creates a new container for a single-agent worker with run parameters
func (m *Manager) CreateSingleAgentContainerWithParams(repoConfig RepositoryConfig, llmConfig LLMConfig, runParams RunParameters) (*ChatContainerInfo, error) {
	containerConfig := WorkerContainerConfig{
		ImageName:           "agentic-single-agent-worker:latest",
		ContainerNamePrefix: "automated-single-agent-run",
		Network:             "agentic-network",
		NATSURL:             "nats://nats:4222",
		AgentType:           "single-agent",
	}
	return m.createContainerWithConfigAndParams(repoConfig, llmConfig, containerConfig, runParams)
}

// CreateSpecialistAgentContainerWithParams creates a new container for a specialist agent (multi-agent) worker with run parameters
func (m *Manager) CreateSpecialistAgentContainerWithParams(repoConfig RepositoryConfig, llmConfig LLMConfig, runParams RunParameters) (*ChatContainerInfo, error) {
	containerConfig := WorkerContainerConfig{
		ImageName:           "agentic-specialist-agent-worker:latest",
		ContainerNamePrefix: "automated-specialists-run",
		Network:             "agentic-network",
		NATSURL:             "nats://nats:4222",
		AgentType:           "specialist",
	}
	return m.createContainerWithConfigAndParams(repoConfig, llmConfig, containerConfig, runParams)
}

// CreateCrewAIContainerWithParams creates a new container for a CrewAI worker with run parameters
func (m *Manager) CreateCrewAIContainerWithParams(repoConfig RepositoryConfig, llmConfig LLMConfig, runParams RunParameters) (*ChatContainerInfo, error) {
	containerConfig := WorkerContainerConfig{
		ImageName:           "agentic-crewai-agent-worker:latest",
		ContainerNamePrefix: "automated-crewai-run",
		Network:             "agentic-network",
		NATSURL:             "nats://nats:4222",
		AgentType:           "crewai",
	}
	return m.createContainerWithConfigAndParams(repoConfig, llmConfig, containerConfig, runParams)
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
