package integration_test

import (
	"encoding/json"
	"time"

	"github.com/nats-io/nats.go"
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

// Shared test IDs
const (
	TestRunID         = "integration-test-run-001"
	TestUserID        = "test-user-001"
	TestProjectID     = "test-project-001"
	TestRepositoryID  = "test-repo-001"
	TestRepositoryURL = "https://github.com/example/test-repo"
	TestTask          = "Write a greeting function and verify it works"
)

var _ = Describe("ControlPlaneNATSFlow", func() {
	It("should receive agent.control.{run_id}.start messages", func() {
		nc := getNATSConnection()

		// prepareAndSendTestRelatedInputs
		controlReceived, controlSub := prepareAndSendTestRelatedInputs(nc)
		defer controlSub.Unsubscribe()

		// FunctionUnderTest
		publishControlStartMessage(nc)

		// ExpectRelatedNatsOutput
		expectControlMessageReceived(controlReceived)
	})
})

func prepareAndSendTestRelatedInputs(nc *nats.Conn) (chan bool, *nats.Subscription) {
	// Subscribe to verify message reception
	controlReceived := make(chan bool, 1)
	controlSub, err := nc.Subscribe("agent.control.>", func(msg *nats.Msg) {
		var controlMsg map[string]interface{}
		if err := json.Unmarshal(msg.Data, &controlMsg); err == nil {
			if controlMsg["run_id"] == TestRunID {
				controlReceived <- true
			}
		}
	})
	Expect(err).NotTo(HaveOccurred())

	return controlReceived, controlSub
}

func publishControlStartMessage(nc *nats.Conn) {
	// FunctionUnderTest: Publish NATS message
	startSubject := "agent.control." + TestRunID + ".start"
	startMessage := map[string]interface{}{
		"message_id":     "test-msg-start-001",
		"run_id":         TestRunID,
		"user_id":        TestUserID,
		"project_id":     TestProjectID,
		"repository_id":  TestRepositoryID,
		"task":           TestTask,
		"mock_mode":      true,
		"agent_type":     "single-agent",
		"llm_provider":   "fake",
		"model_name":     "test-model",
		"timestamp":      time.Now().UTC().Format(time.RFC3339),
		"schema_version": "1.0",
	}

	startMessageBytes, err := json.Marshal(startMessage)
	Expect(err).NotTo(HaveOccurred())

	err = nc.Publish(startSubject, startMessageBytes)
	Expect(err).NotTo(HaveOccurred())
}

func expectControlMessageReceived(received chan bool) {
	// ExpectRelatedNatsOutput: message should be received
	select {
	case <-received:
		// Success - control message received
	case <-time.After(2 * time.Second):
		Fail("Timeout waiting for control message")
	}
}
