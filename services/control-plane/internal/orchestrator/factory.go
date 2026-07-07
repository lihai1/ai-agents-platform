package orchestrator

import (
	"fmt"
)

// ContainerOrchestrator defines the interface for container orchestration
type ContainerOrchestrator interface {
	CreateContainer(config ContainerConfig) (*ContainerResult, error)
	StopContainer(containerID string) error
	RemoveContainer(containerID string) error
	GetContainerStatus(containerID string) (*ContainerStatus, error)
}

// ContainerConfig holds configuration for creating a container
type ContainerConfig struct {
	ChatID        string
	RepositoryURL string
	Branch        string
	Credentials   *RepositoryCredentials
	Image         string
	EnvVars       map[string]string
}

// RepositoryCredentials holds credentials for repository access
type RepositoryCredentials struct {
	Username string
	Token    string
}

// ContainerResult holds the result of container creation
type ContainerResult struct {
	ContainerID string
	Status      string
}

// ContainerStatus holds the status of a container
type ContainerStatus struct {
	ContainerID string
	Status      string
	Running     bool
}

// OrchestratorType defines the type of orchestrator
type OrchestratorType string

const (
	OrchestratorTypeDocker     OrchestratorType = "docker"
	OrchestratorTypeKubernetes OrchestratorType = "kubernetes"
)

// NewOrchestrator creates a new container orchestrator based on type
func NewOrchestrator(orchestratorType OrchestratorType) (ContainerOrchestrator, error) {
	switch orchestratorType {
	case OrchestratorTypeDocker:
		return NewDockerOrchestrator()
	case OrchestratorTypeKubernetes:
		return NewKubernetesOrchestrator()
	default:
		return nil, fmt.Errorf("unsupported orchestrator type: %s", orchestratorType)
	}
}
