package repository

import (
	"database/sql"
	"fmt"

	"github.com/agentic-engineering/control-plane/internal/models"
	"github.com/google/uuid"
)

type UserRepository struct {
	db *sql.DB
}

func NewUserRepository(db *sql.DB) *UserRepository {
	return &UserRepository{db: db}
}

func (r *UserRepository) GetByEmail(email string) (*models.User, error) {
	user := &models.User{}
	query := `SELECT id, email, password_hash, name, created_at, updated_at FROM app.users WHERE email = $1`
	err := r.db.QueryRow(query, email).Scan(
		&user.ID, &user.Email, &user.PasswordHash, &user.Name, &user.CreatedAt, &user.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return user, nil
}

func (r *UserRepository) Create(user *models.User) (*models.User, error) {
	user.ID = uuid.New().String()
	query := `INSERT INTO app.users (id, email, password_hash, name, created_at, updated_at) 
			  VALUES ($1, $2, $3, $4, NOW(), NOW()) RETURNING created_at, updated_at`
	err := r.db.QueryRow(query, user.ID, user.Email, user.PasswordHash, user.Name).Scan(&user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create user: %w", err)
	}
	return user, nil
}

func (r *UserRepository) Get(id string) (*models.User, error) {
	user := &models.User{}
	query := `SELECT id, email, password_hash, name, created_at, updated_at FROM app.users WHERE id = $1`
	err := r.db.QueryRow(query, id).Scan(
		&user.ID, &user.Email, &user.PasswordHash, &user.Name, &user.CreatedAt, &user.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return user, nil
}
