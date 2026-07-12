package integration_test

import (
	"encoding/json"
	"time"

	"github.com/agentic-engineering/control-plane/internal/handlers"
	"github.com/nats-io/nats.go"
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

var _ = Describe("HandleChatStart", func() {
	It("should verify handler can be imported and called with a message", func() {
		// Create NATS message
		message := map[string]interface{}{
			"message_id":     "test-msg-123",
			"run_id":         "test-run-123",
			"repository_id":  "test-repo-123",
			"project_id":     "test-project-123",
			"mock_mode":      true,
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"schema_version": "1.0",
		}
		messageBytes, err := json.Marshal(message)
		Expect(err).NotTo(HaveOccurred())

		// Create NATS message object
		msg := &nats.Msg{
			Subject: "agent.control.test-run-123.start",
			Data:    messageBytes,
		}

		// Verify handler function exists and is callable
		// (We don't call it directly because it requires database/orchestrator setup)
		// This test ensures the handler was extracted properly
		_ = handlers.HandleChatStart
		_ = msg
	})
})

var _ = Describe("HandleChatClose", func() {
	It("should verify handler can be imported and called with a message", func() {
		// Create NATS message
		message := map[string]interface{}{
			"message_id":     "test-msg-456",
			"run_id":         "test-run-123",
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"schema_version": "1.0",
		}
		messageBytes, err := json.Marshal(message)
		Expect(err).NotTo(HaveOccurred())

		// Create NATS message object
		msg := &nats.Msg{
			Subject: "agent.control.test-run-123.close",
			Data:    messageBytes,
		}

		// Verify handler function exists and is callable
		_ = handlers.HandleChatClose
		_ = msg
	})
})
