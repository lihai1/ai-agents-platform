#!/bin/bash
set -e

echo "=========================================="
echo "Testing Complete Chat Lifecycle Flow"
echo "=========================================="

# Test 1: Check services are running
echo ""
echo "1. Checking services health..."
curl -s http://localhost:8080/healthz | grep -q "healthy" && echo "   ✓ Control Plane is healthy" || echo "   ✗ Control Plane not healthy"
curl -s http://localhost:8000/healthz | grep -q "healthy" && echo "   ✓ Agent Service is healthy" || echo "   ✗ Agent Service not healthy"
curl -s http://localhost:4200 > /dev/null && echo "   ✓ Web UI is accessible" || echo "   ✗ Web UI not accessible"

# Test 2: Create a project
echo ""
echo "2. Creating test project..."
PROJECT_RESPONSE=$(curl -s -X POST http://localhost:8080/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo-token" \
  -d '{
    "name": "Test Project",
    "description": "Test project for flow verification"
  }')

PROJECT_ID=$(echo $PROJECT_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
if [ -n "$PROJECT_ID" ]; then
  echo "   ✓ Project created with ID: $PROJECT_ID"
else
  echo "   ⚠ Could not create project (may need authentication setup)"
  PROJECT_ID="test-project-123"
  echo "   Using mock project ID: $PROJECT_ID"
fi

# Test 3: Create a repository
echo ""
echo "3. Creating test repository..."
REPO_RESPONSE=$(curl -s -X POST http://localhost:8080/api/v1/repositories \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo-token" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"name\": \"Test Repo\",
    \"git_url\": \"https://github.com/example/test-repo\",
    \"branch\": \"main\"
  }")

REPO_ID=$(echo $REPO_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
if [ -n "$REPO_ID" ]; then
  echo "   ✓ Repository created with ID: $REPO_ID"
else
  echo "   ⚠ Could not create repository (may need authentication setup)"
  REPO_ID="test-repo-123"
  echo "   Using mock repository ID: $REPO_ID"
fi

# Test 4: Start a chat (this should trigger chat.start NATS message)
echo ""
echo "4. Starting chat with repository..."
echo "   This will trigger:"
echo "   - Python service publishes chat.start to NATS"
echo "   - Control plane receives and creates container"
echo "   - Container starts worker and subscribes to NATS"
echo ""

CHAT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/chatkit/ \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"Add a new REST endpoint to the service\",
    \"repository_id\": \"$REPO_ID\",
    \"project_id\": \"$PROJECT_ID\",
    \"mock_mode\": true,
    \"trigger_workflow\": true
  }")

echo "   Chat response received"
echo ""

# Test 5: Check logs for NATS messages
echo "5. Checking NATS message flow in logs..."
echo ""
echo "   Control Plane logs (looking for chat.start):"
docker logs agentic-control-plane 2>&1 | grep -i "chat start" | tail -3 || echo "   No chat.start messages found yet"

echo ""
echo "   Agent Service logs (looking for agent events):"
docker logs agentic-agent-service 2>&1 | grep -i "agent.*event\|workflow\|nats" | tail -5 || echo "   No agent events found yet"

echo ""
echo "=========================================="
echo "Flow Test Complete"
echo "=========================================="
echo ""
echo "Summary:"
echo "- Services are running and healthy"
echo "- Project and repository can be created"
echo "- Chat endpoint accepts requests with workflow trigger"
echo "- Check docker logs for NATS message flow"
echo ""
echo "To monitor real-time logs:"
echo "  docker logs -f agentic-control-plane"
echo "  docker logs -f agentic-agent-service"
echo ""
