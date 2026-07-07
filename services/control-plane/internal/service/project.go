package service

import (
	"github.com/agentic-engineering/control-plane/internal/models"
	"github.com/agentic-engineering/control-plane/internal/repository"
)

type ProjectService struct {
	projectRepo *repository.ProjectRepository
	orgRepo     *repository.OrganizationRepository
	userRepo    *repository.UserRepository
}

func NewProjectService(projectRepo *repository.ProjectRepository, orgRepo *repository.OrganizationRepository, userRepo *repository.UserRepository) *ProjectService {
	return &ProjectService{
		projectRepo: projectRepo,
		orgRepo:     orgRepo,
		userRepo:    userRepo,
	}
}

func (s *ProjectService) ListProjects() ([]*models.Project, error) {
	return s.projectRepo.List()
}

func (s *ProjectService) CreateProject(orgID, name, description string) (*models.Project, error) {
	project := &models.Project{
		OrganizationID: orgID,
		Name:           name,
		Description:    description,
	}
	return s.projectRepo.Create(project)
}

func (s *ProjectService) GetProject(id string) (*models.Project, error) {
	return s.projectRepo.Get(id)
}

func (s *ProjectService) UpdateProject(id, name, description string) (*models.Project, error) {
	project, err := s.projectRepo.Get(id)
	if err != nil {
		return nil, err
	}
	project.Name = name
	project.Description = description
	return s.projectRepo.Update(project)
}

func (s *ProjectService) DeleteProject(id string) error {
	return s.projectRepo.Delete(id)
}
