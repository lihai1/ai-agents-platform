#!/bin/bash
set -e

echo "Starting agent orchestrator container..."

# Get environment variables
RUN_ID="${RUN_ID}"
REPOSITORY_URL="${REPOSITORY_URL:-/app/fixtures/go-rest-feature}"
BRANCH="${BRANCH:-main}"
GIT_USERNAME="${GIT_USERNAME:-}"
GIT_TOKEN="${GIT_TOKEN:-}"
NATS_URL="${NATS_URL:-nats://nats:4222}"
MOCK_MODE="${MOCK_MODE:-false}"
LLM_PROVIDER="${LLM_PROVIDER:-fake}"
PYTHON_MODULE="${PYTHON_MODULE:-specialist_worker.main}"
PYTHONPATH="${PYTHONPATH:-/app/internal/agents/specialist/src}"

if [ -z "$RUN_ID" ]; then
    echo "Error: RUN_ID environment variable is required"
    exit 1
fi

echo "Run ID: $RUN_ID"
echo "Repository URL: $REPOSITORY_URL"
echo "Branch: $BRANCH"
echo "NATS URL: $NATS_URL"
echo "Mock Mode: $MOCK_MODE"

# Clone repository to workspace (or use mock repository)
echo "Setting up workspace..."
mkdir -p /workspace
cd /workspace

if [ "$MOCK_MODE" = "true" ]; then
    echo "Mock mode enabled - creating mock repository structure..."
    # Create a simple mock repository structure
    mkdir -p /workspace/src
    cat > /workspace/README.md << 'EOF'
# Mock Repository

This is a mock repository for testing purposes.
EOF
    cat > /workspace/src/main.go << 'EOF'
package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
EOF
    cat > /workspace/go.mod << 'EOF'
module mock-repo

go 1.21
EOF
    git init
    git config user.email "mock@example.com"
    git config user.name "Mock User"
    git add .
    git commit -m "Initial commit"
    echo "Mock repository created successfully"
else
    if [ -z "$REPOSITORY_URL" ]; then
        echo "Error: REPOSITORY_URL environment variable is required in non-mock mode"
        exit 1
    fi

    # Use common clone script
    source /app/scripts/clone-repo.sh
fi

# Start the worker process
echo "Starting worker for run $RUN_ID..."
echo "Python Module: $PYTHON_MODULE"
echo "Python Path: $PYTHONPATH"

export RUN_ID="$RUN_ID"
export NATS_URL="$NATS_URL"
export MOCK_MODE="$MOCK_MODE"
export LLM_PROVIDER="$LLM_PROVIDER"
export PYTHONPATH="$PYTHONPATH"

# Run the specified Python module
python -m "$PYTHON_MODULE" --run-id "$RUN_ID"
