package service

import (
	"fmt"
	"log"

	"github.com/agentic-engineering/control-plane/internal/models"
	"github.com/agentic-engineering/control-plane/internal/orchestrator"
	"github.com/agentic-engineering/control-plane/internal/repository"
)

type ChatContainerService struct {
	containerRepo *repository.ChatContainerRepository
	repoRepo      *repository.RepositoryRepository
	manager       *orchestrator.Manager
}

func NewChatContainerService(
	containerRepo *repository.ChatContainerRepository,
	repoRepo *repository.RepositoryRepository,
	manager *orchestrator.Manager,
) *ChatContainerService {
	return &ChatContainerService{
		containerRepo: containerRepo,
		repoRepo:      repoRepo,
		manager:       manager,
	}
}

func (s *ChatContainerService) CreateContainer(runID, repositoryID string, mockMode bool) (*models.ChatContainer, error) {
	var repositoryURL, branch string
	if repositoryID != "" {
		// Get repository details
		repo, err := s.repoRepo.Get(repositoryID)
		if err != nil {
			return nil, fmt.Errorf("failed to get repository: %w", err)
		}
		repositoryURL = repo.GitURL
		branch = repo.Branch
	} else {
		log.Printf("No repository_id provided for run %s, creating container without repository", runID)
	}

	// Create container via orchestrator
	containerInfo, err := s.manager.CreateChatContainer(runID, repositoryURL, branch, nil, mockMode)
	if err != nil {
		return nil, fmt.Errorf("failed to create chat container: %w", err)
	}

	// Save to database
	container := &models.ChatContainer{
		ID:            containerInfo.ID,
		RunID:         runID,
		ContainerID:   containerInfo.ContainerID,
		ContainerName: containerInfo.ContainerName,
		RepositoryURL: containerInfo.RepositoryURL,
		Branch:        containerInfo.Branch,
		Status:        containerInfo.Status,
		CreatedAt:     containerInfo.CreatedAt,
	}

	if err := s.containerRepo.Create(container); err != nil {
		return nil, fmt.Errorf("failed to save chat container: %w", err)
	}

	return container, nil
}

// CreateSingleAgentContainer creates a container for single-agent mode
// TODO: Make agent type selection configurable via request parameters
// Currently hardcoded to use single-agent Docker image
func (s *ChatContainerService) CreateSingleAgentContainer(runID, repositoryID string, mockMode bool) (*models.ChatContainer, error) {
	var repositoryURL, branch string
	if repositoryID != "" {
		// Get repository details
		repo, err := s.repoRepo.Get(repositoryID)
		if err != nil {
			return nil, fmt.Errorf("failed to get repository: %w", err)
		}
		repositoryURL = repo.GitURL
		branch = repo.Branch
	} else {
		log.Printf("No repository_id provided for run %s, creating single-agent container without repository", runID)
	}

	// Create single-agent container via orchestrator
	containerInfo, err := s.manager.CreateSingleAgentContainer(runID, repositoryURL, branch, nil, mockMode)
	if err != nil {
		return nil, fmt.Errorf("failed to create single-agent container: %w", err)
	}

	// Save to database
	container := &models.ChatContainer{
		ID:            containerInfo.ID,
		RunID:         runID,
		ContainerID:   containerInfo.ContainerID,
		ContainerName: containerInfo.ContainerName,
		RepositoryURL: containerInfo.RepositoryURL,
		Branch:        containerInfo.Branch,
		Status:        containerInfo.Status,
		CreatedAt:     containerInfo.CreatedAt,
	}

	if err := s.containerRepo.Create(container); err != nil {
		return nil, fmt.Errorf("failed to save single-agent container: %w", err)
	}

	return container, nil
}

func (s *ChatContainerService) GetContainer(runID string) (*models.ChatContainer, error) {
	return s.containerRepo.GetByRunID(runID)
}

func (s *ChatContainerService) StopContainer(runID string) error {
	container, err := s.containerRepo.GetByRunID(runID)
	if err != nil {
		return fmt.Errorf("failed to get chat container: %w", err)
	}

	// Stop container via orchestrator
	if err := s.manager.StopChatContainer(container.ContainerID); err != nil {
		return fmt.Errorf("failed to stop container: %w", err)
	}

	// Update database
	if err := s.containerRepo.MarkStopped(container.ID); err != nil {
		return fmt.Errorf("failed to mark container as stopped: %w", err)
	}

	return nil
}

func (s *ChatContainerService) RemoveContainer(runID string) error {
	container, err := s.containerRepo.GetByRunID(runID)
	if err != nil {
		return fmt.Errorf("failed to get chat container: %w", err)
	}

	// Remove container via orchestrator
	if err := s.manager.RemoveChatContainer(container.ContainerID); err != nil {
		return fmt.Errorf("failed to remove container: %w", err)
	}

	// Delete from database
	if err := s.containerRepo.Delete(container.ID); err != nil {
		return fmt.Errorf("failed to delete chat container: %w", err)
	}

	return nil
}

func (s *ChatContainerService) ListContainers() ([]*models.ChatContainer, error) {
	return s.containerRepo.List()
}
