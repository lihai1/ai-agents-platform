# Plan: NATS integration tests for agent-service, agent-worker, and control-plane

## One-sentence summary
For each service create one happy-path integration test in its `tests/integration` directory that follows the pattern `prepareAndSendTestRelatedInputs() -> FunctionUnderTest() -> ExpectRelatedNatsOutput()`, using real NATS and DB with simulated data, triggered via each service's local `make dev-env` approach.

## Generic test pattern
Each test follows this human-readable 3-step pattern:
1. `prepareAndSendTestRelatedInputs()` - Set up NATS client, subscriptions, and test data
2. `FunctionUnderTest()` - Call the actual service function being tested
3. `ExpectRelatedNatsOutput()` - Verify the expected NATS message is received

## Detailed test flow
1. **Setup**: Start local development environment (NATS + Postgres) via service-specific `make dev-env`
2. **Prepare**: Call `prepareAndSendTestRelatedInputs()` to set up NATS connections, subscriptions, and test data
3. **Execute**: Call `FunctionUnderTest()` to trigger the service's NATS publishing logic
4. **Verify**: Call `ExpectRelatedNatsOutput()` to assert the expected NATS message is received
5. **Cleanup**: Close connections and unsubscribe from NATS topics

## Scope per service

### agent-service (`tests/integration/test_chatkit_nats_flow.py`)
- **Test**: `test_agent_service_nats_flow`
- **Object under test**: `NatsBridge.publish_agent_start`
- **Helper functions**:
  - `prepareAndSendTestRelatedInputs()` - Sets up NATS client, NatsBridge, and subscription to `agent.control.>`
  - `publishAgentStartMessage()` - Calls `nats_bridge.publish_agent_start()`
  - `expectAgentStartNatsOutput()` - Verifies `agent.control.{run_id}.start` message is received
- **Prerequisite**: `uv run dev-env` (starts local NATS + Postgres via docker-compose-dev.yml)
- **Run**: `uv run test-integration` or `python -m pytest tests/integration/test_chatkit_nats_flow.py -v`
- **Cleanup**: `uv run dev-env-down` to stop development environment

### control-plane (`tests/integration/test_chat_start_nats_flow_test.go`)
- **Test**: `TestControlPlaneNATSFlow`
- **Object under test**: NATS message publishing to `agent.control.>`
- **Helper functions**:
  - `prepareAndSendTestRelatedInputs()` - Sets up NATS subscription to `agent.control.>`
  - `publishControlStartMessage()` - Publishes `agent.control.{run_id}.start` message
  - `expectControlMessageReceived()` - Verifies message is received
- **Prerequisite**: `make dev-env` (starts local NATS + Postgres via docker-compose-dev.yml)
- **Run**: `make test-integration` or `go test -v ./tests/integration/...`
- **Cleanup**: `make dev-env-down` to stop development environment

### agent-worker (`tests/integration/test_worker_nats_flow.py`)
- **Test**: `test_agent_worker_nats_flow`
- **Object under test**: `NATSMessaging.publish_control_ready`
- **Helper functions**:
  - `prepareAndSendTestRelatedInputs()` - Sets up NATS client, JetStream subscription to `agent.control.worker.>`
  - `publishWorkerReadyMessage()` - Calls `nats_messaging.publish_control_ready()`
  - `expectWorkerReadyNatsOutput()` - Verifies `agent.control.worker.{run_id}.ready` message is received
- **Prerequisite**: `make dev-env` (starts local NATS via docker-compose-dev.yml)
- **Run**: `make test-integration` or `python -m pytest tests/integration/test_worker_nats_flow.py -v`
- **Cleanup**: `make dev-env-down` to stop development environment

## Shared test data
All tests use consistent test data to enable end-to-end flow verification:
- **run_id**: `integration-test-run-001`
- **user_id**: `test-user-001`
- **project_id**: `test-project-001`
- **repository_id**: `test-repo-001`
- **repository_url**: `https://github.com/example/test-repo`
- **task**: `Write a greeting function and verify it works`

## Test harness
- **NATS**: `nats://localhost:4222` (started via each service's `make dev-env` or `uv run dev-env`)
- **Postgres**: Service default DBs (started via each service's `make dev-env` or `uv run dev-env`)
- **No test mocking**: Real service code paths with real NATS/DB connections
- **Local execution**: Tests run locally without Docker containers for the test itself
- **Environment variables**: Tests use default NATS_URL or can be set via environment

## Expected output per service
Each test asserts the NATS message that the service itself is responsible for:
- **agent-service**: `agent.control.{run_id}.start` (published by `NatsBridge.publish_agent_start`)
- **control-plane**: `agent.control.{run_id}.start` (published to verify message reception)
- **agent-worker**: `agent.control.worker.{run_id}.ready` (published by `NATSMessaging.publish_control_ready`)

## Reproducibility instructions
To run all integration tests:

1. **agent-service**:
   ```bash
   cd services/agent-service
   uv run dev-env          # Start NATS + Postgres
   uv run test-integration # Run integration tests
   uv run dev-env-down     # Cleanup
   ```

2. **control-plane**:
   ```bash
   cd services/control-plane
   make dev-env            # Start NATS + Postgres
   make test-integration   # Run integration tests
   make dev-env-down       # Cleanup
   ```

3. **agent-worker**:
   ```bash
   cd services/agent-worker
   make dev-env            # Start NATS
   make test-integration   # Run integration tests
   make dev-env-down       # Cleanup
   ```

## Test isolation
Each test is designed to run independently:
- Tests use unique message IDs to avoid conflicts
- Subscriptions are cleaned up after each test
- NATS connections are properly closed
- No shared state between test runs
