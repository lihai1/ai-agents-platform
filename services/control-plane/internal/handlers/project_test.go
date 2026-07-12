package handlers_test

import (
	"net/http"
	"net/http/httptest"

	"github.com/agentic-engineering/control-plane/internal/handlers"
	"github.com/agentic-engineering/control-plane/internal/service"
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

var _ = Describe("ProjectHandler", func() {
	var handler *handlers.ProjectHandler
	var mockService *service.ProjectService

	BeforeEach(func() {
		mockService = &service.ProjectService{}
		handler = handlers.NewProjectHandler(mockService)
	})

	Describe("ListProjects", func() {
		It("should return 200 OK", func() {
			req := httptest.NewRequest("GET", "/api/v1/projects", nil)
			w := httptest.NewRecorder()

			handler.ListProjects(w, req)

			Expect(w.Code).To(Equal(http.StatusOK))
		})
	})
})
