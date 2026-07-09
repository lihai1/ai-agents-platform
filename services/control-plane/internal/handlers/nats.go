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
	MessageID     string `json:"message_id"`
	RunID         string `json:"run_id"`
	RepositoryID  string `json:"repository_id"`
	ProjectID     string `json:"project_id"`
	MockMode      bool   `json:"mock_mode"`
	AgentType     string `json:"agent_type"` // "multi-agent" or "single-agent"
	Timestamp     string `json:"timestamp"`
	SchemaVersion string `json:"schema_version"`
}

// ChatCloseMessage represents a chat close message from NATS
type ChatCloseMessage struct {
	MessageID     string `json:"message_id"`
	RunID         string `json:"run_id"`
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
	log.Printf("[NATS RECEIVE] Run ID: %s, Repository ID: %s, Mock Mode: %v, Agent Type: %s", chatMsg.RunID, chatMsg.RepositoryID, chatMsg.MockMode, chatMsg.AgentType)

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
	if chatMsg.AgentType == "single-agent" {
		_, err = chatContainerService.CreateSingleAgentContainer(chatMsg.RunID, chatMsg.RepositoryID, chatMsg.MockMode)
		log.Printf("[NATS RECEIVE] Creating single-agent container for run %s", chatMsg.RunID)
	} else {
		// Default to multi-agent mode
		_, err = chatContainerService.CreateContainer(chatMsg.RunID, chatMsg.RepositoryID, chatMsg.MockMode)
		log.Printf("[NATS RECEIVE] Creating multi-agent container for run %s", chatMsg.RunID)
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
