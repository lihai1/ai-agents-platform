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

// CreateSpecialistAgentContainer creates a container for specialist agent (multi-agent) mode
func (s *ChatContainerService) CreateSpecialistAgentContainer(repoConfig orchestrator.RepositoryConfig, llmConfig orchestrator.LLMConfig) (*models.ChatContainer, error) {
	repositoryURL := repoConfig.RepositoryURL
	branch := repoConfig.Branch
	runID := repoConfig.RunID

	if repoConfig.RepositoryID != "" {
		// Get repository details
		repo, err := s.repoRepo.Get(repoConfig.RepositoryID)
		if err != nil {
			return nil, fmt.Errorf("failed to get repository: %w", err)
		}
		repositoryURL = repo.GitURL
		branch = repo.Branch
	} else {
		log.Printf("No repository_id provided for run %s, creating container without repository", runID)
	}

	// Update repoConfig with actual repository details
	repoConfig.RepositoryURL = repositoryURL
	repoConfig.Branch = branch

	// Create specialist agent container via orchestrator
	containerInfo, err := s.manager.CreateSpecialistAgentContainer(repoConfig, llmConfig)
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
func (s *ChatContainerService) CreateSingleAgentContainer(repoConfig orchestrator.RepositoryConfig, llmConfig orchestrator.LLMConfig) (*models.ChatContainer, error) {
	repositoryURL := repoConfig.RepositoryURL
	branch := repoConfig.Branch
	runID := repoConfig.RunID

	if repoConfig.RepositoryID != "" {
		// Get repository details
		repo, err := s.repoRepo.Get(repoConfig.RepositoryID)
		if err != nil {
			return nil, fmt.Errorf("failed to get repository: %w", err)
		}
		repositoryURL = repo.GitURL
		branch = repo.Branch
	} else {
		log.Printf("No repository_id provided for run %s, creating single-agent container without repository", runID)
	}

	// Update repoConfig with actual repository details
	repoConfig.RepositoryURL = repositoryURL
	repoConfig.Branch = branch

	// Create single-agent container via orchestrator
	containerInfo, err := s.manager.CreateSingleAgentContainer(repoConfig, llmConfig)
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

// CreateSpecialistAgentContainerWithParams creates a container for specialist agent (multi-agent) mode with run parameters
func (s *ChatContainerService) CreateSpecialistAgentContainerWithParams(repoConfig orchestrator.RepositoryConfig, llmConfig orchestrator.LLMConfig, runParams orchestrator.RunParameters) (*models.ChatContainer, error) {
	repositoryURL := repoConfig.RepositoryURL
	branch := repoConfig.Branch
	runID := repoConfig.RunID

	if repoConfig.RepositoryID != "" {
		// Get repository details
		repo, err := s.repoRepo.Get(repoConfig.RepositoryID)
		if err != nil {
			return nil, fmt.Errorf("failed to get repository: %w", err)
		}
		repositoryURL = repo.GitURL
		branch = repo.Branch
	} else {
		log.Printf("No repository_id provided for run %s, creating container without repository", runID)
	}

	// Update repoConfig with actual repository details
	repoConfig.RepositoryURL = repositoryURL
	repoConfig.Branch = branch

	// Create specialist agent container via orchestrator with params
	containerInfo, err := s.manager.CreateSpecialistAgentContainerWithParams(repoConfig, llmConfig, runParams)
	if err != nil {
		return nil, fmt.Errorf("failed to create chat container: %w", err)
	}

	// Save to database
	container := &models.ChatContainer{
		ID:            containerInfo.ID,
		RunID:         runID,
		ContainerID:   containerInfo.ContainerID,
		ContainerName: containerInfo.ContainerName,
		RepositoryURL: repositoryURL,
		Branch:        branch,
		Status:        containerInfo.Status,
		CreatedAt:     containerInfo.CreatedAt,
	}

	if err := s.containerRepo.Create(container); err != nil {
		return nil, fmt.Errorf("failed to save chat container: %w", err)
	}

	return container, nil
}

// CreateSingleAgentContainerWithParams creates a container for single-agent mode with run parameters
func (s *ChatContainerService) CreateSingleAgentContainerWithParams(repoConfig orchestrator.RepositoryConfig, llmConfig orchestrator.LLMConfig, runParams orchestrator.RunParameters) (*models.ChatContainer, error) {
	repositoryURL := repoConfig.RepositoryURL
	branch := repoConfig.Branch
	runID := repoConfig.RunID

	if repoConfig.RepositoryID != "" {
		// Get repository details
		repo, err := s.repoRepo.Get(repoConfig.RepositoryID)
		if err != nil {
			return nil, fmt.Errorf("failed to get repository: %w", err)
		}
		repositoryURL = repo.GitURL
		branch = repo.Branch
	} else {
		log.Printf("No repository_id provided for run %s, creating single-agent container without repository", runID)
	}

	// Update repoConfig with actual repository details
	repoConfig.RepositoryURL = repositoryURL
	repoConfig.Branch = branch

	// Create single-agent container via orchestrator with params
	containerInfo, err := s.manager.CreateSingleAgentContainerWithParams(repoConfig, llmConfig, runParams)
	if err != nil {
		return nil, fmt.Errorf("failed to create single-agent container: %w", err)
	}

	// Save to database
	container := &models.ChatContainer{
		ID:            containerInfo.ID,
		RunID:         runID,
		ContainerID:   containerInfo.ContainerID,
		ContainerName: containerInfo.ContainerName,
		RepositoryURL: repositoryURL,
		Branch:        branch,
		Status:        containerInfo.Status,
		CreatedAt:     containerInfo.CreatedAt,
	}

	if err := s.containerRepo.Create(container); err != nil {
		return nil, fmt.Errorf("failed to save single-agent container: %w", err)
	}

	return container, nil
}
