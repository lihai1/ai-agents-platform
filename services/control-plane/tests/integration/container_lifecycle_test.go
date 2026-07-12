package integration_test

import (
	"encoding/json"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

var _ = Describe("ContainerLifecyclePublishStart", func() {
	It("should publish agent start message", func() {
		nc := getNATSConnection()

		subject := "agent.control.test-run-123.start"

		// Publish agent start message
		message := map[string]interface{}{
			"message_id":     "test-msg-789",
			"run_id":         "test-run-123",
			"user_id":        "test-user-123",
			"project_id":     "test-project-123",
			"repository_id":  "test-repo-123",
			"task":           "Test task",
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

var _ = Describe("ContainerLifecyclePublishCancel", func() {
	It("should publish close message", func() {
		nc := getNATSConnection()

		subject := "agent.control.test-run-123.close"

		// Publish close message
		message := map[string]interface{}{
			"message_id":     "test-msg-790",
			"run_id":         "test-run-123",
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

var _ = Describe("ContainerLifecycleFullFlow", func() {
	It("should publish start and close messages", func() {
		nc := getNATSConnection()

		runID := "test-run-lifecycle-123"
		startSubject := "agent.control." + runID + ".start"
		closeSubject := "agent.control." + runID + ".close"

		// Publish start message
		startMessage := map[string]interface{}{
			"message_id":     "test-msg-start",
			"run_id":         runID,
			"user_id":        "test-user-123",
			"project_id":     "test-project-123",
			"repository_id":  "test-repo-123",
			"task":           "Test task",
			"mock_mode":      false,
			"agent_type":     "specialist",
			"llm_provider":   "ollama",
			"model_name":     "qwen3.5:9b",
			"api_key":        "",
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"schema_version": "1.0",
		}
		startBytes, err := json.Marshal(startMessage)
		Expect(err).NotTo(HaveOccurred())

		err = nc.Publish(startSubject, startBytes)
		Expect(err).NotTo(HaveOccurred())

		// Wait a bit for message to be processed
		time.Sleep(100 * time.Millisecond)

		// Publish close message
		closeMessage := map[string]interface{}{
			"message_id":     "test-msg-close",
			"run_id":         runID,
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"schema_version": "1.0",
		}
		closeBytes, err := json.Marshal(closeMessage)
		Expect(err).NotTo(HaveOccurred())

		err = nc.Publish(closeSubject, closeBytes)
		Expect(err).NotTo(HaveOccurred())

		// Wait a bit for message to be processed
		time.Sleep(100 * time.Millisecond)
	})
})
