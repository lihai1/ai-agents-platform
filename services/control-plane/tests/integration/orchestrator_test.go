package integration_test

import (
	"encoding/json"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

var _ = Describe("OrchestratorWorkerReady", func() {
	It("should publish worker ready message", func() {
		nc := getNATSConnection()

		subject := "agent.control.container.ready"

		// Publish worker ready message
		message := map[string]interface{}{
			"message_id":     "test-msg-worker-ready",
			"run_id":         "test-run-123",
			"status":         "ready",
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"schema_version": "1.0",
		}
		messageBytes, err := json.Marshal(message)
		Expect(err).NotTo(HaveOccurred())

		err = nc.Publish(subject, messageBytes)
		Expect(err).NotTo(HaveOccurred())

		// Wait a bit for message to be processed
		time.Sleep(100 * time.Millisecond)
	})
})

var _ = Describe("OrchestratorCommandReception", func() {
	It("should publish orchestrator command", func() {
		nc := getNATSConnection()

		subject := "agent.control.test-run-orch-456.start"

		// Publish orchestrator command
		message := map[string]interface{}{
			"message_id":     "test-msg-orch",
			"run_id":         "test-run-orch-456",
			"user_id":        "test-user-456",
			"project_id":     "test-project-456",
			"repository_id":  "test-repo-456",
			"task":           "Orchestrator test task",
			"mock_mode":      false,
			"agent_type":     "specialist",
			"llm_provider":   "ollama",
			"model_name":     "qwen3.5:9b",
			"api_key":        "",
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"schema_version": "1.0",
		}
		messageBytes, err := json.Marshal(message)
		Expect(err).NotTo(HaveOccurred())

		err = nc.Publish(subject, messageBytes)
		Expect(err).NotTo(HaveOccurred())

		// Wait a bit for message to be processed
		time.Sleep(100 * time.Millisecond)
	})
})
