package handlers

import (
	"encoding/json"
	"io"
	"net/http"
)

type OllamaHandler struct {
	ollamaBaseURL string
}

func NewOllamaHandler(ollamaBaseURL string) *OllamaHandler {
	return &OllamaHandler{
		ollamaBaseURL: ollamaBaseURL,
	}
}

type OllamaModel struct {
	Name       string `json:"name"`
	ModifiedAt string `json:"modified_at"`
	Size       int64  `json:"size"`
}

type OllamaModelsResponse struct {
	Models []OllamaModel `json:"models"`
}

func (h *OllamaHandler) ListModels(w http.ResponseWriter, r *http.Request) {
	// Call Ollama API to list models
	resp, err := http.Get(h.ollamaBaseURL + "/api/tags")
	if err != nil {
		http.Error(w, "Failed to connect to Ollama: "+err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		http.Error(w, "Ollama returned non-200 status: "+string(body), http.StatusBadGateway)
		return
	}

	var modelsResp OllamaModelsResponse
	if err := json.NewDecoder(resp.Body).Decode(&modelsResp); err != nil {
		http.Error(w, "Failed to parse Ollama response: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(modelsResp.Models)
}
