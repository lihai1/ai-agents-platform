package handlers

import (
	"encoding/json"
	"log"

	"github.com/agentic-engineering/control-plane/internal/orchestrator"
	"github.com/agentic-engineering/control-plane/internal/repository"
	"github.com/agentic-engineering/control-plane/internal/service"
	"github.com/nats-io/nats.go"
)

// ChatStartMessage represents a chat start message from NATS
type ChatStartMessage struct {
	MessageID       string  `json:"message_id"`
	RunID           string  `json:"run_id"`
	RepositoryID    string  `json:"repository_id"`
	ProjectID       string  `json:"project_id"`
	UserID          string  `json:"user_id"`
	Task            string  `json:"task"`
	MockMode        bool    `json:"mock_mode"`
	AgentType       string  `json:"agent_type"`   // "multi-agent" or "single-agent"
	LLMProvider     string  `json:"llm_provider"` // "fake", "ollama", "openai", "anthropic"
	ModelName       string  `json:"model_name"`   // Model name for the LLM provider
	APIKey          string  `json:"api_key"`      // API key for non-Ollama providers
	ChatkitThreadID string  `json:"chatkit_thread_id"`
	MaxTokens       int     `json:"max_tokens"`
	MaxCost         float64 `json:"max_cost"`
	MaxRepairCount  int     `json:"max_repair_count"`
	Timestamp       string  `json:"timestamp"`
	SchemaVersion   string  `json:"schema_version"`
}

// ChatCloseMessage represents a chat close message from NATS
type ChatCloseMessage struct {
	MessageID     string `json:"message_id"`
	RunID         string `json:"run_id"`
	Timestamp     string `json:"timestamp"`
	SchemaVersion string `json:"schema_version"`
}

// ChatCancelMessage represents a chat cancel message from NATS
type ChatCancelMessage struct {
	MessageID     string `json:"message_id"`
	RunID         string `json:"run_id"`
	Timestamp     string `json:"timestamp"`
	SchemaVersion string `json:"schema_version"`
}

// ChatResumeMessage represents a chat resume message from NATS
type ChatResumeMessage struct {
	MessageID     string `json:"message_id"`
	RunID         string `json:"run_id"`
	RepositoryID  string `json:"repository_id"`
	ProjectID     string `json:"project_id"`
	MockMode      bool   `json:"mock_mode"`
	AgentType     string `json:"agent_type"`
	LLMProvider   string `json:"llm_provider"`
	ModelName     string `json:"model_name"`
	APIKey        string `json:"api_key"`
	Timestamp     string `json:"timestamp"`
	SchemaVersion string `json:"schema_version"`
}

// HandleChatStart handles chat start messages from NATS
func HandleChatStart(msg *nats.Msg, chatContainerService *service.ChatContainerService, containerManager *orchestrator.Manager, repoRepo *repository.RepositoryRepository, nc *nats.Conn, js nats.JetStreamContext) {
	var chatMsg ChatStartMessage
	if err := json.Unmarshal(msg.Data, &chatMsg); err != nil {
		log.Printf("[NATS RECEIVE] Failed to unmarshal chat start message: %v", err)
		return
	}

	log.Printf("[NATS RECEIVE] Received chat start message on subject: %s", msg.Subject)
	log.Printf("[NATS RECEIVE] Chat start payload: %s", string(msg.Data))
	log.Printf("[NATS RECEIVE] Run ID: %s, Repository ID: %s, Mock Mode: %v, Agent Type: %s, LLM Provider: %s", chatMsg.RunID, chatMsg.RepositoryID, chatMsg.MockMode, chatMsg.AgentType, chatMsg.LLMProvider)

	// Get repository details for logging when a repository_id is provided
	if chatMsg.RepositoryID != "" {
		repo, err := repoRepo.Get(chatMsg.RepositoryID)
		if err != nil {
			log.Printf("[NATS RECEIVE] Failed to get repository for run %s: %v", chatMsg.RunID, err)
			return
		}
		log.Printf("[NATS RECEIVE] Repository URL for run %s: %s", chatMsg.RunID, repo.GitURL)
	} else {
		log.Printf("[NATS RECEIVE] No repository_id provided for run %s, skipping repository validation", chatMsg.RunID)
	}

	// Create a chat container record (real container or mock record)
	// TODO: Make agent type selection more robust with validation
	// Currently defaults to multi-agent if not specified
	var err error
	repoConfig := orchestrator.RepositoryConfig{
		RunID:        chatMsg.RunID,
		RepositoryID: chatMsg.RepositoryID,
		Credentials:  nil,
	}
	llmConfig := orchestrator.LLMConfig{
		MockMode:    chatMsg.MockMode,
		LLMProvider: chatMsg.LLMProvider,
		ModelName:   chatMsg.ModelName,
		APIKey:      chatMsg.APIKey,
	}
	runParams := orchestrator.RunParameters{
		UserID:          chatMsg.UserID,
		ProjectID:       chatMsg.ProjectID,
		RepositoryID:    chatMsg.RepositoryID,
		Task:            chatMsg.Task,
		ChatkitThreadID: chatMsg.ChatkitThreadID,
		MaxTokens:       chatMsg.MaxTokens,
		MaxCost:         chatMsg.MaxCost,
		MaxRepairCount:  chatMsg.MaxRepairCount,
	}

	if chatMsg.AgentType == "single-agent" {
		_, err = chatContainerService.CreateSingleAgentContainerWithParams(repoConfig, llmConfig, runParams)
		log.Printf("[NATS RECEIVE] Creating single-agent container for run %s with LLM provider %s", chatMsg.RunID, chatMsg.LLMProvider)
	} else {
		// Default to multi-agent mode
		_, err = chatContainerService.CreateSpecialistAgentContainerWithParams(repoConfig, llmConfig, runParams)
		log.Printf("[NATS RECEIVE] Creating multi-agent container for run %s with LLM provider %s", chatMsg.RunID, chatMsg.LLMProvider)
	}

	if err != nil {
		log.Printf("[NATS RECEIVE] Failed to create container for run %s: %v", chatMsg.RunID, err)
		return
	}

	if chatMsg.MockMode {
		log.Printf("[NATS RECEIVE] Mock mode enabled for run %s; mock-worker will handle this run", chatMsg.RunID)
	} else {
		log.Printf("[NATS RECEIVE] Successfully started worker container for run %s", chatMsg.RunID)
	}

	// Worker will publish its own ready signal via container-start.sh
	// Control-plane no longer publishes worker ready - worker handles this
	log.Printf("[NATS RECEIVE] Worker container started and will publish ready signal for run %s", chatMsg.RunID)
}

// HandleChatClose handles chat close messages from NATS
func HandleChatClose(msg *nats.Msg, chatContainerService *service.ChatContainerService, containerManager *orchestrator.Manager) {
	var chatMsg ChatCloseMessage
	if err := json.Unmarshal(msg.Data, &chatMsg); err != nil {
		log.Printf("[NATS RECEIVE] Failed to unmarshal chat close message: %v", err)
		return
	}

	log.Printf("[NATS RECEIVE] Received chat close message on subject: %s", msg.Subject)
	log.Printf("[NATS RECEIVE] Chat close payload: %s", string(msg.Data))
	log.Printf("[NATS RECEIVE] Run ID: %s", chatMsg.RunID)

	// Get container info before stopping
	container, err := chatContainerService.GetContainer(chatMsg.RunID)
	if err != nil {
		log.Printf("[NATS RECEIVE] Failed to get container for run %s: %v", chatMsg.RunID, err)
		return
	}

	// Stop and remove worker container
	if container != nil && container.ContainerID != "" {
		log.Printf("[NATS RECEIVE] Stopping worker container for run %s", chatMsg.RunID)
		if err := containerManager.StopWorker(container.ContainerID); err != nil {
			log.Printf("[NATS RECEIVE] Failed to stop worker for run %s: %v", chatMsg.RunID, err)
			return
		}
		log.Printf("[NATS RECEIVE] Successfully stopped worker container for run %s", chatMsg.RunID)
	}

	// Clean up database record
	if err := chatContainerService.RemoveContainer(chatMsg.RunID); err != nil {
		log.Printf("[NATS RECEIVE] Failed to remove container record for run %s: %v", chatMsg.RunID, err)
		return
	}

	log.Printf("[NATS RECEIVE] Successfully terminated worker for run %s", chatMsg.RunID)
}

// HandleChatCancel handles chat cancel messages from NATS
func HandleChatCancel(msg *nats.Msg, chatContainerService *service.ChatContainerService, containerManager *orchestrator.Manager) {
	var chatMsg ChatCancelMessage
	if err := json.Unmarshal(msg.Data, &chatMsg); err != nil {
		log.Printf("[NATS RECEIVE] Failed to unmarshal chat cancel message: %v", err)
		return
	}

	log.Printf("[NATS RECEIVE] Received chat cancel message on subject: %s", msg.Subject)
	log.Printf("[NATS RECEIVE] Chat cancel payload: %s", string(msg.Data))
	log.Printf("[NATS RECEIVE] Run ID: %s", chatMsg.RunID)

	// Get container info before stopping
	container, err := chatContainerService.GetContainer(chatMsg.RunID)
	if err != nil {
		log.Printf("[NATS RECEIVE] Failed to get container for run %s: %v", chatMsg.RunID, err)
		return
	}

	// Stop and remove worker container
	if container != nil && container.ContainerID != "" {
		log.Printf("[NATS RECEIVE] Stopping worker container for run %s", chatMsg.RunID)
		if err := containerManager.StopWorker(container.ContainerID); err != nil {
			log.Printf("[NATS RECEIVE] Failed to stop worker for run %s: %v", chatMsg.RunID, err)
			return
		}
		log.Printf("[NATS RECEIVE] Successfully stopped worker container for run %s", chatMsg.RunID)
	}

	// Clean up database record
	if err := chatContainerService.RemoveContainer(chatMsg.RunID); err != nil {
		log.Printf("[NATS RECEIVE] Failed to remove container record for run %s: %v", chatMsg.RunID, err)
		return
	}

	log.Printf("[NATS RECEIVE] Successfully cancelled worker for run %s", chatMsg.RunID)
}

// HandleChatResume handles chat resume messages from NATS
func HandleChatResume(msg *nats.Msg, chatContainerService *service.ChatContainerService, containerManager *orchestrator.Manager, repoRepo *repository.RepositoryRepository, nc *nats.Conn, js nats.JetStreamContext) {
	var chatMsg ChatResumeMessage
	if err := json.Unmarshal(msg.Data, &chatMsg); err != nil {
		log.Printf("[NATS RECEIVE] Failed to unmarshal chat resume message: %v", err)
		return
	}

	log.Printf("[NATS RECEIVE] Received chat resume message on subject: %s", msg.Subject)
	log.Printf("[NATS RECEIVE] Chat resume payload: %s", string(msg.Data))
	log.Printf("[NATS RECEIVE] Run ID: %s, Repository ID: %s, Mock Mode: %v, Agent Type: %s, LLM Provider: %s", chatMsg.RunID, chatMsg.RepositoryID, chatMsg.MockMode, chatMsg.AgentType, chatMsg.LLMProvider)

	// Get repository details for logging when a repository_id is provided
	if chatMsg.RepositoryID != "" {
		repo, err := repoRepo.Get(chatMsg.RepositoryID)
		if err != nil {
			log.Printf("[NATS RECEIVE] Failed to get repository for run %s: %v", chatMsg.RunID, err)
			return
		}
		log.Printf("[NATS RECEIVE] Repository URL for run %s: %s", chatMsg.RunID, repo.GitURL)
	} else {
		log.Printf("[NATS RECEIVE] No repository_id provided for run %s, skipping repository validation", chatMsg.RunID)
	}

	// Create a new chat container record (real container or mock record)
	var err error
	repoConfig := orchestrator.RepositoryConfig{
		RunID:        chatMsg.RunID,
		RepositoryID: chatMsg.RepositoryID,
		Credentials:  nil,
	}
	llmConfig := orchestrator.LLMConfig{
		MockMode:    chatMsg.MockMode,
		LLMProvider: chatMsg.LLMProvider,
		ModelName:   chatMsg.ModelName,
		APIKey:      chatMsg.APIKey,
	}
	runParams := orchestrator.RunParameters{
		UserID:          "", // userID not available on resume
		ProjectID:       chatMsg.ProjectID,
		RepositoryID:    chatMsg.RepositoryID,
		Task:            "", // task not available on resume
		ChatkitThreadID: "", // chatkitThreadID not available on resume
		MaxTokens:       0,  // maxTokens not available on resume
		MaxCost:         0,  // maxCost not available on resume
		MaxRepairCount:  2,  // maxRepairCount default
	}

	if chatMsg.AgentType == "single-agent" {
		_, err = chatContainerService.CreateSingleAgentContainerWithParams(repoConfig, llmConfig, runParams)
		log.Printf("[NATS RECEIVE] Recreating single-agent container for run %s with LLM provider %s", chatMsg.RunID, chatMsg.LLMProvider)
	} else {
		// Default to multi-agent mode
		_, err = chatContainerService.CreateSpecialistAgentContainerWithParams(repoConfig, llmConfig, runParams)
		log.Printf("[NATS RECEIVE] Recreating multi-agent container for run %s with LLM provider %s", chatMsg.RunID, chatMsg.LLMProvider)
	}

	if err != nil {
		log.Printf("[NATS RECEIVE] Failed to recreate container for run %s: %v", chatMsg.RunID, err)
		return
	}

	if chatMsg.MockMode {
		log.Printf("[NATS RECEIVE] Mock mode enabled for run %s; mock-worker will handle this run", chatMsg.RunID)
	} else {
		log.Printf("[NATS RECEIVE] Successfully restarted worker container for run %s", chatMsg.RunID)
	}

	log.Printf("[NATS RECEIVE] Worker container restarted and will publish ready signal for run %s", chatMsg.RunID)
}
