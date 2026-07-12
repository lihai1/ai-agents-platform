# Complete Chat-to-Agent Flow Documentation

## Overview
This document describes the complete flow from UI start page to agent execution, including all NATS messages, service interactions, and state transitions.

## Architecture Components

### Services
1. **Angular UI** (port 4200) - User interface
2. **Python Agent Service** (port 8000) - ChatKit and workflow orchestration
3. **Go Control Plane** (port 8080) - Container management and repository access
4. **NATS JetStream** (port 4222) - Message broker
5. **PostgreSQL** (port 5432) - Data persistence
6. **Agent Worker** - Executes LangGraph workflows (runs in container or as separate process)

### Key Tables
- `chatkit_threads` - Chat thread persistence
- `chatkit_items` - Chat messages
- `chat_containers` - Container lifecycle tracking
- `agent_runs` - Workflow execution tracking
- `agent_events` - Event history

## Complete Flow

### Step 1: User Starts New Project
**Location:** `apps/web/src/app/projects/projects.component.ts`

1. User navigates to `/` (projects page)
2. UI loads projects from agent-service (proxied to control-plane): `GET /api/projects`
3. User clicks "New Project" or selects existing project
4. User optionally selects GitHub repository (or none)
5. User clicks "Start Chat"

**Navigation:** `router.navigate(['/chat'], { queryParams: { project_id, repository_id } })`

### Step 2: Chat Window Opens
**Location:** `apps/web/src/app/chat/chat.component.ts`

1. Angular navigates to `/chat?project_id=X&repository_id=Y`
2. ChatComponent loads ChatKit client script from `/assets/chatkit-client.js`
3. ChatKit initializes with:
   - `apiUrl`: Python service endpoint
   - `projectId`: From query params
   - `repositoryId`: From query params (optional)
   - `triggerWorkflow`: Checkbox state

### Step 3: User Sends First Message
**Location:** ChatKit client → `services/agent-service/internal/chatkit/router.py`

1. User types message and clicks send
2. ChatKit sends: `POST /api/chatkit/`
   ```json
   {
     "message": "Add a login feature",
     "repository_id": "repo-123",
     "project_id": "proj-456",
     "trigger_workflow": true,
     "mock_mode": false
   }
   ```

### Step 4: Python Service Starts Chat
**Location:** `services/agent-service/internal/chatkit/router.py:115-162`

**Actions:**
1. Create or get thread ID
2. Save user message to database

**NATS Message 1 - Run Start:**
```python
# Subject: agent.control.{run_id}.start
await nats.publish_chat_start(
    run_id=thread_id,
    repository_id=repository_id,
    project_id=project_id,
    user_id=user_id,
    task=message,
    chatkit_thread_id=thread_id,
    mock_mode=False,
    max_tokens=0,
    max_cost=0.0,
    max_repair_count=2
)
```

**Log Output:**
```
[NATS PUBLISH] Publishing chat start {message_id} to subject: agent.control.{run_id}.start
[NATS PUBLISH] Chat start payload: {...}
```

3. Subscribe to global event stream for agent events
```python
await nats.subscribe_to_global_events(event_handler=handle_chat_event)
```

### Step 5: Control Plane Creates Container
**Location:** `services/control-plane/cmd/server/main.go:153-175`

**NATS Subscriber:** `agent.control.>`

**Actions:**
1. Receive agent.control.{run_id}.start message
   ```
   [NATS RECEIVE] Received chat start message on subject: agent.control.{run_id}.start
   [NATS RECEIVE] Chat start payload: {...}
   [NATS RECEIVE] Run ID: {run_id}, Repository ID: {repo_id}, Mock Mode: false
   ```

2. Create Docker container with environment variables:
   ```go
   chatContainerService.CreateSpecialistAgentContainerWithParams(
       runID, repositoryID, mockMode, llmProvider, apiKey,
       userID, projectID, task, chatkitThreadID, maxTokens, maxCost, maxRepairCount
   )
   ```
   - Container includes: RUN_ID, USER_ID, TASK, PROJECT_ID, REPOSITORY_ID, etc.
   - Container clones repository
   - Container starts worker process

3. Save ChatContainer record to database

**Log Output:**
```
[NATS RECEIVE] Creating multi-agent container for run {run_id} with LLM provider {llm_provider}
[NATS RECEIVE] Successfully created container for run {run_id}
```

### Step 6: Worker Auto-Starts Workflow
**Location:** `services/agent-worker/app/worker.py:31-69`

**Actions:**
1. Container starts worker process
2. Worker connects to NATS
3. Worker reads run parameters from environment variables:
   - RUN_ID, USER_ID, TASK, PROJECT_ID, REPOSITORY_ID, etc.
4. Worker auto-starts workflow immediately:
   ```python
   await handle_run_start(
       self.run_id,
       {
           "user_id": os.getenv("USER_ID"),
           "project_id": os.getenv("PROJECT_ID"),
           "repository_id": os.getenv("REPOSITORY_ID"),
           "task": os.getenv("TASK"),
           "max_repair_count": int(os.getenv("MAX_REPAIR_COUNT", "2")),
           "mock_mode": os.getenv("MOCK_MODE", "false").lower() == "true",
       },
       create_run,
       get_checkpointer
   )
   ```
5. Worker publishes ready signal

**Log Output:**
```
[WORKER] Starting agent worker for run {run_id}
[WORKER] Auto-starting run {run_id}
[WORKER] Agent worker started and auto-started run {run_id}
```

### Step 7: Orchestrator Agent Executes in Sequence
**Location:** `services/agent-worker/internal/workflow/graph.py`

**State Transitions:**
1. CREATED
2. PREPARING_WORKSPACE
3. SCOUTING
4. PLANNING
5. DESIGNING
6. IMPLEMENTING
7. TESTING
8. REVIEWING
9. VERIFYING
10. COMPLETED (or REPAIRING → back to IMPLEMENTING)

**For Each State Transition:**

**NATS Message 2+ - Agent State Updates:**
```python
# Subject: agent.user.{uid}.events.{rid}.state.{state}
await nats.publish_event(
    event_type=state.lower(),
    run_id=run_id,
    user_id=user_id,
    payload={
        "state": state,
        "agent": agent_name,
        "data": {...}
    }
)
```

**Log Output:**
```
[NATS PUBLISH] Publishing event {message_id} to subject: agent.user.{uid}.events.{rid}.state.scouting
[NATS PUBLISH] Event payload: {...}
[NATS PUBLISH] Successfully published event {message_id} to agent.user.{uid}.events.{rid}.state.scouting
```

### Step 8: Python Service Receives Agent Events
**Location:** `services/agent-service/internal/chatkit/server.py`

**NATS Subscriber:** `agent.user.*.events.>` (global event stream)

**Actions:**
1. Receive event
   ```
   [NATS RECEIVE] Received event on subject: agent.user.{uid}.events.{rid}.state.scouting
   [NATS RECEIVE] Event payload: {...}
   [NATS RECEIVE] Received agent event for run {run_id}: {...}
   ```

2. Update chat state in database

3. Forward to UI via SSE (Server-Sent Events)

### Step 9: UI Displays Agent Updates
**Location:** ChatKit client (SSE stream)

**UI Receives:**
```
data: {"state": "scouting", "agent": "repo-scout", "message": "Analyzing repository structure..."}
data: {"state": "planning", "agent": "solution-planner", "message": "Creating implementation plan..."}
data: {"state": "implementing", "agent": "go-developer", "message": "Writing code..."}
...
```

**User Observes:**
- Real-time agent activity in chat window
- State transitions and progress updates
- Agent messages and artifacts

### Step 10: Human Intervention (if needed)
**Trigger:** Protected action (push, PR, network access, etc.)

**State:** WAITING_APPROVAL

**NATS Message - Approval Request:**
```python
# Subject: agent.user.{uid}.events.{rid}.state.waiting_approval
await nats.publish_event(
    event_type="waiting_approval",
    run_id=run_id,
    user_id=user_id,
    payload={
        "approval_id": approval_id,
        "action": "push_code",
        "reason": "Push to main branch requires approval"
    }
)
```

**UI Shows:** Approval dialog

**User Action:** Approve or Reject

**API Call:** `POST /api/agent/runs/{run_id}/approvals/{approval_id}/approve` or `/reject`

**NATS Message - Resume Command:**
```python
# Subject: agent.control.{run_id}.resume
await nats.publish_chat_resume(
    run_id=run_id,
    repository_id=repository_id,
    project_id=project_id,
    mock_mode=False,
    agent_type="multi-agent",
    llm_provider="ollama",
    api_key=""
)
```

**Control Plane Actions:**
1. Receives `agent.control.{run_id}.resume`
2. Recreates container with same parameters
3. Worker auto-starts and resumes from checkpoint

### Step 11: Workflow Completion
**Final State:** COMPLETED, FAILED, CANCELLED, or BUDGET_EXCEEDED

**NATS Message - Final Event:**
```python
# Subject: agent.user.{uid}.events.{rid}.state.completed
await nats.publish_event(
    event_type="completed",
    run_id=run_id,
    user_id=user_id,
    payload={
        "status": "completed",
        "artifacts": [...],
        "summary": "..."
    }
)
```

**Worker Log:**
```
[WORKER] Run for run {run_id} completed with status completed
```

**UI Shows:** Final status and artifacts

### Step 12: Chat Termination (Optional)
**Trigger:** User closes chat

**API Call:** `POST /api/chatkit/close/{thread_id}`

**NATS Message - Chat Close:**
```python
# Subject: agent.control.{run_id}.close
await nats.publish_chat_close(run_id=run_id)
```

**Log Output:**
```
[NATS PUBLISH] Publishing chat close {message_id} to subject: agent.control.{run_id}.close
[NATS PUBLISH] Chat close payload: {...}
```

**Control Plane Actions:**
1. Receive chat.close message
   ```
   [NATS RECEIVE] Received chat close message on subject: agent.control.{run_id}.close
   [NATS RECEIVE] Chat close payload: {...}
   [NATS RECEIVE] Run ID: {run_id}
   ```

2. Stop container
3. Remove container
4. Update ChatContainer status
   ```
   [NATS RECEIVE] Successfully terminated container for run {run_id}
   ```

## NATS Subject Patterns

### Control Signals (Agent-Service → Control-Plane)
- `agent.control.{run_id}.start` - Start run with all parameters (user_id, task, project_id, etc.)
- `agent.control.{run_id}.close` - Close run (stop & remove container)
- `agent.control.{run_id}.resume` - Resume run (recreate container)

### Event Subjects (Worker → Agent-Service)
- `agent.user.{uid}.events.{rid}.state.{event_type}` - State transition events
  - `created`, `preparing_workspace`, `scouting`, `planning`, `designing`
  - `implementing`, `testing`, `reviewing`, `verifying`, `repairing`
  - `waiting_approval`, `completed`, `failed`, `cancelled`, `budget_exceeded`

### Close Signal
- `agent.control.{run_id}.close` - Trigger container termination

### Subscription Patterns
- `agent.control.>` - All control signals (Control Plane subscription)
- `agent.user.*.events.>` - All agent events (Agent Service global event stream)

## Error Handling

### No Response After 30 Seconds
**Possible Causes:**
1. NATS not running
2. Control plane not subscribed to agent.control.>
3. Container creation failed
4. Worker not running or failed to auto-start
5. Workflow execution error

**Debug Steps:**
1. Check NATS connection: `nc.IsConnected()`
2. Check control plane logs for agent.control.{run_id}.start receipt
3. Check container status: `docker ps`
4. Check worker logs for auto-start errors
5. Check PostgreSQL for run record

### Container Creation Fails
**Symptoms:** No agent.user.{uid}.events.{rid}.state.* events published

**Debug:**
- Check control plane logs
- Check Docker daemon status
- Check repository access credentials

### Workflow Doesn't Start
**Symptoms:** Container created but no state events

**Debug:**
- Check worker logs for auto-start errors
- Check environment variables in container
- Check PostgreSQL connection
- Check LangGraph checkpointer setup

## Testing

### E2E Test Flow
1. Navigate to projects page
2. Create or select project
3. Optionally add GitHub repository
4. Click "Start Chat"
5. Verify chat window opens
6. Send message with trigger_workflow=true
7. Wait for first agent update (max 30s)
8. Verify agent state appears in chat
9. Verify subsequent updates appear

### Mock Mode
Set `mock_mode=true` to skip:
- Actual container creation
- Real repository cloning
- LLM API calls

## Monitoring

### Key Metrics
- Chat start latency (UI → container ready)
- Workflow trigger latency (command → first state)
- State transition frequency
- Message delivery success rate
- Container lifecycle duration

### Log Correlation
All logs include `chat_id` for correlation:
- `[NATS PUBLISH] ... chat {chat_id}`
- `[NATS RECEIVE] ... chat {chat_id}`
- `[WORKER] ... chat {chat_id}`

## Configuration

### Environment Variables
- `NATS_URL` - NATS server URL (default: nats://localhost:4222)
- `CONTROL_PLANE_URL` - Control plane URL (default: http://localhost:8080)
- `MOCK_MODE` - Enable mock mode (default: false)
- `MOCK_DOCKER` - Mock Docker operations (default: false)

### Timeouts
- Container creation: 30s
- Workflow execution: Configurable per run
- NATS message delivery: Automatic retry with exponential backoff
- SSE reconnection: Automatic with Last-Event-ID

## Troubleshooting

### Symptom: No chat.start message received
**Fix:** Verify NATS connection in Python service

### Symptom: Container created but no agent.chat.{chat_id}.start
**Fix:** Check control plane NATS publish permissions

### Symptom: run.start command sent but worker doesn't respond
**Fix:** Verify worker is subscribed to correct subject pattern

### Symptom: Agent events published but UI doesn't update
**Fix:** Check Python service subscription to agent.user.*.events.>

### Symptom: UI shows "Workflow started" but no updates
**Fix:** Check worker logs for execution errors
