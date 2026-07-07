package repository

import (
	"database/sql"
	"fmt"

	"github.com/agentic-engineering/control-plane/internal/models"
	"github.com/google/uuid"
)

type ProjectRepository struct {
	db *sql.DB
}

func NewProjectRepository(db *sql.DB) *ProjectRepository {
	return &ProjectRepository{db: db}
}

func (r *ProjectRepository) List() ([]*models.Project, error) {
	query := `SELECT id, organization_id, name, description, created_at, updated_at FROM app.projects`
	rows, err := r.db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var projects []*models.Project
	for rows.Next() {
		project := &models.Project{}
		err := rows.Scan(&project.ID, &project.OrganizationID, &project.Name, &project.Description, &project.CreatedAt, &project.UpdatedAt)
		if err != nil {
			return nil, err
		}
		projects = append(projects, project)
	}
	return projects, nil
}

func (r *ProjectRepository) Create(project *models.Project) (*models.Project, error) {
	project.ID = uuid.New().String()
	query := `INSERT INTO app.projects (id, organization_id, name, description, created_at, updated_at) 
			  VALUES ($1, $2, $3, $4, NOW(), NOW()) RETURNING created_at, updated_at`
	err := r.db.QueryRow(query, project.ID, project.OrganizationID, project.Name, project.Description).Scan(&project.CreatedAt, &project.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create project: %w", err)
	}
	return project, nil
}

func (r *ProjectRepository) Get(id string) (*models.Project, error) {
	project := &models.Project{}
	query := `SELECT id, organization_id, name, description, created_at, updated_at FROM app.projects WHERE id = $1`
	err := r.db.QueryRow(query, id).Scan(&project.ID, &project.OrganizationID, &project.Name, &project.Description, &project.CreatedAt, &project.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return project, nil
}

func (r *ProjectRepository) Update(project *models.Project) (*models.Project, error) {
	query := `UPDATE app.projects SET name = $1, description = $2, updated_at = NOW() WHERE id = $3 RETURNING updated_at`
	err := r.db.QueryRow(query, project.Name, project.Description, project.ID).Scan(&project.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to update project: %w", err)
	}
	return project, nil
}

func (r *ProjectRepository) Delete(id string) error {
	query := `DELETE FROM app.projects WHERE id = $1`
	_, err := r.db.Exec(query, id)
	if err != nil {
		return fmt.Errorf("failed to delete project: %w", err)
	}
	return nil
}
