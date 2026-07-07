package service

import (
	"github.com/agentic-engineering/control-plane/internal/models"
	"github.com/agentic-engineering/control-plane/internal/repository"
)

type RepositoryService struct {
	repoRepo    *repository.RepositoryRepository
	projectRepo *repository.ProjectRepository
}

func NewRepositoryService(repoRepo *repository.RepositoryRepository, projectRepo *repository.ProjectRepository) *RepositoryService {
	return &RepositoryService{
		repoRepo:    repoRepo,
		projectRepo: projectRepo,
	}
}

func (s *RepositoryService) ListRepositories(projectID string) ([]*models.Repository, error) {
	return s.repoRepo.List(projectID)
}

func (s *RepositoryService) CreateRepository(projectID, name, gitURL, branch string) (*models.Repository, error) {
	repo := &models.Repository{
		ProjectID: projectID,
		Name:      name,
		GitURL:    gitURL,
		Branch:    branch,
	}
	return s.repoRepo.Create(repo)
}

func (s *RepositoryService) GetRepository(id string) (*models.Repository, error) {
	return s.repoRepo.Get(id)
}

func (s *RepositoryService) UpdateRepository(id, name, gitURL, branch string) (*models.Repository, error) {
	repo, err := s.repoRepo.Get(id)
	if err != nil {
		return nil, err
	}
	repo.Name = name
	repo.GitURL = gitURL
	repo.Branch = branch
	return s.repoRepo.Update(repo)
}

func (s *RepositoryService) DeleteRepository(id string) error {
	return s.repoRepo.Delete(id)
}
