package repository

import (
	"database/sql"
	"fmt"

	"github.com/agentic-engineering/control-plane/internal/models"
	"github.com/google/uuid"
)

type RepositoryRepository struct {
	db *sql.DB
}

func NewRepositoryRepository(db *sql.DB) *RepositoryRepository {
	return &RepositoryRepository{db: db}
}

func (r *RepositoryRepository) List(projectID string) ([]*models.Repository, error) {
	query := `SELECT id, project_id, name, git_url, branch, created_at, updated_at FROM app.repositories WHERE project_id = $1`
	rows, err := r.db.Query(query, projectID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var repos []*models.Repository
	for rows.Next() {
		repo := &models.Repository{}
		err := rows.Scan(&repo.ID, &repo.ProjectID, &repo.Name, &repo.GitURL, &repo.Branch, &repo.CreatedAt, &repo.UpdatedAt)
		if err != nil {
			return nil, err
		}
		repos = append(repos, repo)
	}
	return repos, nil
}

func (r *RepositoryRepository) Create(repo *models.Repository) (*models.Repository, error) {
	repo.ID = uuid.New().String()
	query := `INSERT INTO app.repositories (id, project_id, name, git_url, branch, created_at, updated_at) 
			  VALUES ($1, $2, $3, $4, $5, NOW(), NOW()) RETURNING created_at, updated_at`
	err := r.db.QueryRow(query, repo.ID, repo.ProjectID, repo.Name, repo.GitURL, repo.Branch).Scan(&repo.CreatedAt, &repo.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create repository: %w", err)
	}
	return repo, nil
}

func (r *RepositoryRepository) Get(id string) (*models.Repository, error) {
	repo := &models.Repository{}
	query := `SELECT id, project_id, name, git_url, branch, created_at, updated_at FROM app.repositories WHERE id = $1`
	err := r.db.QueryRow(query, id).Scan(&repo.ID, &repo.ProjectID, &repo.Name, &repo.GitURL, &repo.Branch, &repo.CreatedAt, &repo.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return repo, nil
}

func (r *RepositoryRepository) Update(repo *models.Repository) (*models.Repository, error) {
	query := `UPDATE app.repositories SET name = $1, git_url = $2, branch = $3, updated_at = NOW() WHERE id = $4 RETURNING updated_at`
	err := r.db.QueryRow(query, repo.Name, repo.GitURL, repo.Branch, repo.ID).Scan(&repo.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to update repository: %w", err)
	}
	return repo, nil
}

func (r *RepositoryRepository) Delete(id string) error {
	query := `DELETE FROM app.repositories WHERE id = $1`
	_, err := r.db.Exec(query, id)
	if err != nil {
		return fmt.Errorf("failed to delete repository: %w", err)
	}
	return nil
}
