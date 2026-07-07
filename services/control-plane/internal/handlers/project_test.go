package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/agentic-engineering/control-plane/internal/service"
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

func TestProjectHandler(t *testing.T) {
	RegisterFailHandler(Fail)
	RunSpecs(t, "ProjectHandler Suite")
}

var _ = Describe("ProjectHandler", func() {
	var handler *ProjectHandler
	var mockService *service.ProjectService

	BeforeEach(func() {
		mockService = &service.ProjectService{}
		handler = NewProjectHandler(mockService)
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
