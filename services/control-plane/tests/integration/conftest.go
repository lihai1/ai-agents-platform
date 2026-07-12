package integration_test

import (
	"os"
	"time"

	"github.com/nats-io/nats.go"
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

var nc *nats.Conn

var _ = BeforeSuite(func() {
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = "nats://localhost:4222"
	}

	var err error
	nc, err = nats.Connect(natsURL)
	Expect(err).NotTo(HaveOccurred())

	// Wait for connection to be established
	time.Sleep(100 * time.Millisecond)
})

var _ = AfterSuite(func() {
	if nc != nil {
		nc.Close()
	}
})

// Helper function to get NATS connection
func getNATSConnection() *nats.Conn {
	return nc
}
