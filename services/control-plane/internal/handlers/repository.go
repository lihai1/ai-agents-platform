package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/agentic-engineering/control-plane/internal/service"
)

type RepositoryHandler struct {
	repositoryService *service.RepositoryService
}

func NewRepositoryHandler(repositoryService *service.RepositoryService) *RepositoryHandler {
	return &RepositoryHandler{repositoryService: repositoryService}
}

func (h *RepositoryHandler) ListRepositories(w http.ResponseWriter, r *http.Request) {
	projectID := r.URL.Query().Get("project_id")
	repos, err := h.repositoryService.ListRepositories(projectID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(repos)
}

func (h *RepositoryHandler) CreateRepository(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ProjectID string `json:"project_id"`
		Name      string `json:"name"`
		GitURL    string `json:"git_url"`
		Branch    string `json:"branch"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	repo, err := h.repositoryService.CreateRepository(req.ProjectID, req.Name, req.GitURL, req.Branch)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(repo)
}

func (h *RepositoryHandler) GetRepository(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	repo, err := h.repositoryService.GetRepository(id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(repo)
}

func (h *RepositoryHandler) UpdateRepository(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	var req struct {
		Name   string `json:"name"`
		GitURL string `json:"git_url"`
		Branch string `json:"branch"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	repo, err := h.repositoryService.UpdateRepository(id, req.Name, req.GitURL, req.Branch)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(repo)
}

func (h *RepositoryHandler) DeleteRepository(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if err := h.repositoryService.DeleteRepository(id); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
