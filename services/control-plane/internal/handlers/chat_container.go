package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/agentic-engineering/control-plane/internal/service"
	"github.com/gorilla/mux"
)

type ChatContainerHandler struct {
	containerService *service.ChatContainerService
}

func NewChatContainerHandler(containerService *service.ChatContainerService) *ChatContainerHandler {
	return &ChatContainerHandler{containerService: containerService}
}

type CreateContainerRequest struct {
	ChatID       string `json:"chat_id"`
	RepositoryID string `json:"repository_id"`
	MockMode     bool   `json:"mock_mode"`
}

func (h *ChatContainerHandler) CreateContainer(w http.ResponseWriter, r *http.Request) {
	var req CreateContainerRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	container, err := h.containerService.CreateContainer(req.ChatID, req.RepositoryID, req.MockMode)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(container)
}

func (h *ChatContainerHandler) GetContainer(w http.ResponseWriter, r *http.Request) {
	chatID := mux.Vars(r)["chat_id"]
	if chatID == "" {
		http.Error(w, "chat_id is required", http.StatusBadRequest)
		return
	}

	container, err := h.containerService.GetContainer(chatID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(container)
}

func (h *ChatContainerHandler) StopContainer(w http.ResponseWriter, r *http.Request) {
	chatID := mux.Vars(r)["chat_id"]
	if chatID == "" {
		http.Error(w, "chat_id is required", http.StatusBadRequest)
		return
	}

	if err := h.containerService.StopContainer(chatID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func (h *ChatContainerHandler) RemoveContainer(w http.ResponseWriter, r *http.Request) {
	chatID := mux.Vars(r)["chat_id"]
	if chatID == "" {
		http.Error(w, "chat_id is required", http.StatusBadRequest)
		return
	}

	if err := h.containerService.RemoveContainer(chatID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func (h *ChatContainerHandler) ListContainers(w http.ResponseWriter, r *http.Request) {
	containers, err := h.containerService.ListContainers()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(containers)
}
