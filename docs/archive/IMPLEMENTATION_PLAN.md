# Complete Implementation Plan - All Phases

This plan establishes the complete agentic engineering platform across 11 phases, combining Angular UI and Python service development, using latest Angular 22, latest Go with ginkgo testing, and supporting Ollama plus cloud models.

## Summary

Implement the complete agentic engineering platform through 11 phases, starting with foundation (Go, PostgreSQL, Docker Compose), then combining Angular UI with Python ChatKit in Phase 2, followed by LangGraph workflow, skills, workspace isolation, implementation agents, testing/review/verification, human approval, activity UX, NATS separation, and hardening. A first-flow E2E smoke test uses the `mock-worker` container to validate the ChatKit streaming path without real LLM calls.

## Current State

- Repository is empty (greenfield project)
- Target: Multi-service platform with Angular/Go/Python/PostgreSQL
- Model support: Ollama + cloud providers (OpenAI, Anthropic)
- Git provider: GitHub only
- Solo project
- Angular: Latest version 22+
- Go: Latest version with ginkgo testing framework
- Reference template: stat-tree-server
- Architecture diagrams exist in agentic-engineering-platform-docs/docs/architecture/diagrams/

## Phase 1: Foundation (Go + Infrastructure)

### Deliverables
- Monorepo structure with apps/, services/, deploy/, contracts/, docs/
- Go control plane service (latest Go version) following stat-tree-server pattern
- PostgreSQL with app schema (users, organizations, projects, repositories)
- Docker Compose orchestration (PostgreSQL + migrate + backend)
- golang-migrate for Go migrations (not Liquibase)
- ginkgo testing framework for Go
- Health and readiness endpoints (/healthz, /readyz)
- JWT validation middleware (golang-jwt/jwt)
- Internal service authentication tokens
- CI pipeline (GitHub Actions)
- Makefile with targets: build, run, test, migrate-up, migrate-down, lint, fmt
- README with quick start
- .env.example for configuration

### Acceptance
- Single command (make dev) starts Go service and PostgreSQL
- Go service passes health checks (GET /healthz, /readyz)
- Database migrations initialize empty schemas (make migrate-up)
- ginkgo tests run successfully (make test)
- CI pipeline runs successfully on push
- Standard Go project layout (cmd/server, internal/)

## Phase 2: Angular UI + Python ChatKit Vertical Slice (Combined)

### Deliverables
- Angular 22+ application with standalone components
- Core module with HTTP client, error handling, config
- Auth module with JWT handling (interceptor for API calls)
- Projects module (skeleton - list/select projects)
- Chat module with ChatKit integration
- ChatKit host component (loads ChatKit client script)
- Run context component (skeleton - displays run metadata)
- Python FastAPI service structure (uv for dependency management)
- ChatKit custom server implementation (AegisChatKitServer with SSE)
- ChatKit PostgreSQL store (agent.chatkit_threads, agent.chatkit_items)
- ChatKit NATS bridge (subscribe to `agent.events.{run_id}.>`)
- ChatKit event mapper (progress_update, thread.item.done)
- Simple LangChain agent with Ollama/OpenAI support (langchain-openai, langchain-anthropic)
- Streaming response handling (SSE from ChatKit)
- Mock worker for first-flow E2E testing (no real LLM calls)
- Thread persistence (PostgreSQL-backed)
- User/thread authorization (JWT validation)
- Angular ChatKit wrapper (framework-agnostic component)
- Model factory (Ollama, OpenAI, Anthropic - provider abstraction)
- Health endpoints for Python service (/healthz, /readyz)
- Alembic migrations for agent schema
- Dockerfiles for Angular and Python
- Root docker-compose.yml updated to include Angular and Python services

### Acceptance
- User sends message through Angular UI (ChatKit component)
- Response streams into ChatKit via SSE (real-time streaming)
- Mock worker publishes progress and completed events for first-flow E2E
- ChatKit server maps NATS events to progress_update and thread.item.done SSE events
- Refreshing page preserves thread (thread persistence)
- Cross-user thread access is rejected (authorization)
- Angular can call both Go and Python APIs (HTTP client)
- Python service passes health checks (/healthz, /readyz)
- Model factory supports Ollama and cloud providers (config-based)
- ChatKit custom server responds to POST /chatkit

## Phase 3: LangGraph Workflow Skeleton

### Deliverables
- EngineeringState TypedDict (aligned with diagram 02-langgraph-workflow.mmd)
- Main StateGraph with all required nodes (CREATED, PREPARING_WORKSPACE, SCOUTING, PLANNING, DESIGNING, IMPLEMENTING, TESTING, REVIEWING, VERIFYING, REPAIRING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, BUDGET_EXCEEDED)
- PostgreSQL checkpointer setup (langgraph-checkpoint-postgres)
- Run tables (agent_runs, agent_steps, agent_events) in agent schema
- Fake deterministic nodes for all phases (no real model calls)
- SSE event stream implementation (GET /agent/v1/runs/{run_id}/events)
- Event adapter (LangGraph events → public AgentEvent schema)
- Cancellation flag and propagation (cancel_requested_at check at node boundaries)
- LangGraph thread ID management (graph_thread_id = run_id)
- Run API endpoints (POST /agent/v1/runs, GET /agent/v1/runs/{run_id}, POST /agent/v1/runs/{run_id}/cancel)
- Event replay with Last-Event-ID (SSE reconnection support)
- LangSmith tracing integration (metadata: run_id, chatkit_thread_id, project_id, repository_id)

### Acceptance
- Fake run traverses every required phase (state machine validation)
- Checkpoints are persisted (PostgreSQL checkpointer)
- Run survives browser reconnection (event replay with Last-Event-ID)
- Events replay using Last-Event-ID (SSE reconnection)
- Cancellation creates terminal state (CANCELLED state reached)
- LangSmith traces correlate with run IDs (metadata integration)
- All terminal states are reachable (COMPLETED, FAILED, CANCELLED, BUDGET_EXCEEDED)

## Phase 4: Skills and Read-Only Agents

### Deliverables
- Skill registry implementation (loads .agents/minimal or .agents/full)
- Skill loader (minimal and full profiles from .agents directory)
- Skill validation (skill.yaml schema, output.schema.json validation)
- Skill snapshots with content hashing (immutable per run)
- skills-lead agent with structured output (SkillsLeadDecision Pydantic model)
- repo-scout agent with structured output (RepositorySummary Pydantic model)
- solution-planner agent with structured output (ImplementationPlan Pydantic model)
- Read-only repository tools (list_files, read_file, search_files, read_repository_metadata)
- Repository metadata tools (from Go control plane API)
- Agent factory with LangChain create_agent (langchain.agents.create_agent)
- Context isolation per specialist (minimal context passed to each agent)
- Skill versioning and hash recording (stored in agent.skill_snapshots)
- .agents directory structure with skill.yaml, SKILL.md, output.schema.json

### Acceptance
- Repository task generates repository summary, selected agents, implementation plan (structured outputs)
- Skill versions and hashes are recorded in skill_snapshots table
- No files are modified (read-only tools only)
- Structured outputs are validated against JSON schemas
- skills-lead selects appropriate specialists based on task

## Phase 5: Workspace Isolation

### Deliverables
- Docker workspace manager (docker-py SDK)
- Disposable container per run (ephemeral containers)
- Repository clone with short-lived credentials (from Go control plane)
- Run-specific branch creation (git checkout -b run-{run_id})
- CPU, memory, PID limits (docker container resource limits)
- Network disabled by default (network_mode: none)
- Command timeout enforcement (per-command and total run timeout)
- Workspace cleanup after completion (container removal, volume cleanup)
- Build/test command allowlists (whitelist of safe commands)
- Workspace lease tracking (agent.workspace_leases table)
- Integration with Go service for repository metadata (GET /api/v1/repositories/{id})
- Non-root user in containers (security best practice)
- No Docker socket mount (prevents container escape)
- Dedicated writable workspace volume (isolated from host)

### Acceptance
- Workspace cannot access unrelated host files (volume isolation)
- Workspace has no Docker socket (security restriction)
- Timeout kills subprocesses (process group termination)
- Repository diff remains isolated (no push without approval)
- Workspace cleanup works on completion/failure (automatic cleanup)
- Network is disabled by default (no external access)

## Phase 6: Implementation Agents

### Deliverables
- Go developer agent (ImplementationResult Pydantic model)
- Angular developer agent (ImplementationResult Pydantic model)
- Angular UI developer agent (ImplementationResult Pydantic model)
- DevOps developer agent (ImplementationResult Pydantic model)
- Implementation subgraph with parallel execution (independent agents run concurrently)
- File ownership detection (prevent overlapping modifications)
- Overlapping file scope serialization (sequential execution for conflicting files)
- Write and patch tools (write_file, apply_patch with validation)
- Diff artifact generation (git diff stored as artifact)
- Unrelated change detection (compare actual changes vs planned changes)
- Git diff and status tools (git_status, git_diff)
- Implementation results aggregation (merge results from all developers)

### Acceptance
- Agents modify fixture repositories (test repositories)
- Changes are limited to planned files (implementation_plan.files_expected_to_change)
- Complete diff artifact is generated (agent.agent_artifacts with kind=code_diff)
- Unrelated changes are detected and rejected (safety check)
- Parallel execution works for non-overlapping files (performance optimization)
- Sequential execution for overlapping files (correctness guarantee)

## Phase 7: Testing, Review, and Verification

### Deliverables
- Backend test engineer agent (TestResult Pydantic model)
- Angular test engineer agent (TestResult Pydantic model)
- Code reviewer agent (ReviewResult Pydantic model with ReviewFinding)
- Completion verifier agent (VerificationResult Pydantic model with CriterionResult)
- Two-attempt repair loop (max_repair_count = 2)
- Test execution in workspace (run_tests tool with allowlist)
- Review findings with severity levels (blocking, high, medium, low)
- Acceptance criteria evaluation (map results to implementation_plan.acceptance_criteria)
- Verification result mapping (VerificationResult.accepted boolean)
- Repair limit enforcement (repair_count >= max_repair_count → FAILED)
- Test report artifacts (agent.agent_artifacts with kind=test_report)
- Review report artifacts (agent.agent_artifacts with kind=review_report)
- Verification report artifacts (agent.agent_artifacts with kind=verification_report)

### Acceptance
- Workflow cannot complete without testing and verification (mandatory phases)
- Failed verification enters repair (REPAIRING state)
- Repair stops after configured limit (max_repair_count check)
- Final result maps evidence to acceptance criteria (CriterionResult for each criterion)
- Test reports and review reports are generated (artifacts stored)
- Blocking review findings prevent completion (decision=changes_required)

## Phase 8: Human Approval

### Deliverables
- LangGraph interrupt implementation (langgraph.types.interrupt)
- Approval API endpoints (POST /agent/v1/runs/{run_id}/approvals/{approval_id}/approve, POST /agent/v1/runs/{run_id}/approvals/{approval_id}/reject)
- Approval dialog in Angular (ApprovalDialogComponent)
- Resume with Command (langgraph.Command with approval decision)
- Rejection behavior (continue without action or mark as FAILED)
- Approval audit trail (agent.agent_approvals table with decision, decided_by, decided_at)
- Approval-required tools (push, PR, network, credentials, protected files)
- Serialized paused state (LangGraph checkpoint stores interrupt state)
- Authorization check for approvers (user must have project access)
- Approval widget in ChatKit (shows pending approvals)
- WAITING_APPROVAL state handling (aligned with diagram 02-langgraph-workflow.mmd)

### Acceptance
- Protected action pauses (WAITING_APPROVAL state reached)
- Run remains persisted (checkpoint survives service restart)
- Approval resumes the same graph thread (resume with Command)
- Rejection prevents execution (tool not executed)
- Approval cannot be submitted by unauthorized user (authorization check)
- Approval decisions are audited (agent.agent_approvals record)
- Sequence diagram 05-human-approval-sequence.mmd is implemented

## Phase 9: Activity and Artifact UX

### Deliverables
- Hierarchical agent timeline component (AgentActivityComponent)
- Event filters (by agent, by type, by phase)
- Diff viewer component (DiffViewerComponent with syntax highlighting)
- Mermaid artifact viewer (renders architecture.mmd diagrams)
- Test report view (TestReportComponent with pass/fail summary)
- Review view (ReviewComponent with findings by severity)
- Verification view (VerificationComponent with criteria results)
- Usage summary component (UsageSummaryComponent with tokens, cost, duration)
- Artifact opening from activity events (click to view artifact)
- Token and cost display (per-agent and total usage)
- Duration display (per-phase and total duration)
- SSE reconnection handling (Last-Event-ID support)
- Collapsible tool events (expand/collapse details)
- Copy sanitized errors (copy error messages to clipboard)
- Approval actions from activity panel (approve/reject buttons)

### Acceptance
- Every agent and tool has visible sanitized status (timeline shows all activity)
- Artifacts open from activity events (click to view)
- Browser reconnection restores state (event replay)
- Diff viewer shows changes clearly (syntax highlighting, line numbers)
- Mermaid diagrams render correctly (architecture diagrams display)
- Sequence diagram 04-live-agent-events-sequence.mmd is implemented

## Phase 10: NATS Worker Separation

### Deliverables
- NATS JetStream setup (nats-py SDK)
- Worker process separation (API and worker as separate processes)
- Run command stream (AGENT_COMMANDS stream with durable consumer)
- Event publication stream (AGENT_EVENTS stream)
- Durable consumers (ack-based delivery)
- Idempotent command handling (message ID deduplication)
- Message IDs and retry policy (exponential backoff)
- Dead-letter handling (failed messages to DLQ)
- Event schema versioning (schema_version field in events)
- Run-ID correlation (correlation_id in messages)
- Worker recovery logic (restart and resume from checkpoint)
- Command subjects (agent.commands.run.start, agent.commands.run.cancel, agent.commands.run.resume)
- Event subjects (agent.events.{run_id})
- PostgreSQL remains source of truth (NATS for transport only)

### Acceptance
- API restart does not lose queued work (durable JetStream)
- Duplicate commands do not duplicate runs (idempotency check)
- Worker failure produces recoverable or terminal state (checkpoint recovery)
- Events are published reliably (JetStream persistence)
- Dead-letter messages are handled (DLQ monitoring)

## Phase 11: Hardening and Evaluation

### Deliverables
- Threat model documentation (docs/threat-model/)
- Prompt-injection tests (tests/security/prompt_injection.py)
- Secret-redaction tests (tests/security/secret_redaction.py)
- Resource-exhaustion tests (tests/security/resource_exhaustion.py)
- Authorization tests (tests/security/authorization.py)
- Evaluation fixture repositories (tests/fixtures/):
  - Go REST feature repository
  - Angular component feature repository
  - Docker Compose change repository
  - Broken implementation requiring repair
  - Repository with prompt-injection text
  - Repository with fake secrets
  - Repository with failing tests
- LangSmith datasets and evaluations (evaluation/ datasets)
- Operational documentation (docs/operations/)
- Dependency scanning (GitHub Dependabot, Snyk)
- Container image scanning (Trivy, Docker Scout)
- Kubernetes manifests (deploy/kubernetes/ - only after Docker Compose is stable)
- Security audit (external audit or self-assessment)
- Performance metrics (Prometheus/Grafana setup)
- Rate limiting (per-user, per-organization)
- CORS allowlist configuration
- Request-size limits
- Output size limits

### Acceptance
- Prompt-injection attempts are detected and blocked (security tests pass)
- Secrets are redacted from all outputs (redaction tests pass)
- Resource limits are enforced (exhaustion tests pass)
- Authorization boundaries are respected (authorization tests pass)
- Evaluation suite measures agent performance (LangSmith evaluation results)
- Security audit passes (no critical vulnerabilities)
- Deployment documentation is complete (runbook, troubleshooting guide)

## Overall Definition of Done

1. User can select repository and submit coding task (Angular UI + Go API)
2. ChatKit triggers skills-lead (ChatKit action → LangGraph run)
3. LangGraph controls full workflow (StateGraph with all phases)
4. Specialist agents created through LangChain (create_agent factory)
5. Every required phase executes (CREATED → COMPLETED state machine)
6. Activity panel displays sanitized events (SSE with Last-Event-ID replay)
7. Repository changes occur only in isolated workspace (Docker container)
8. Relevant tests execute (test agents in workspace)
9. Code review executes (code-reviewer agent)
10. Completion verification executes (completion-verifier agent)
11. Sensitive operations pause through LangGraph interrupts (WAITING_APPROVAL state)
12. Approval resumes same graph (Command-based resume)
13. Events survive browser reconnection (PostgreSQL event store + SSE replay)
14. LangGraph checkpoints survive service restart (PostgreSQL checkpointer)
15. Run history is persistent (agent_runs table)
16. Artifacts are accessible (agent_artifacts table + object storage)
17. Cancellation works (CANCELLED state, sequence diagram 06-cancel-run-sequence.mmd)
18. Budget limits work (BUDGET_EXCEEDED state)
19. Repair limits work (max_repair_count enforcement)
20. LangSmith traces correlate with run IDs (metadata integration)
21. No secrets or hidden reasoning displayed (sanitization and redaction)
22. Entire platform starts through one documented command (make dev)

## Key Technical Decisions

- **Angular**: Latest version 22+ with standalone components
- **Go**: Latest version with ginkgo testing framework
- **Python**: 3.12+ with uv for dependency management
- **Database**: PostgreSQL 16 with separate schemas
- **Migrations**: golang-migrate (Go), Alembic (Python)
- **Orchestration**: LangGraph with PostgreSQL checkpointer
- **Agents**: LangChain create_agent
- **Models**: LangChain with Ollama, OpenAI, Anthropic backends
- **Chat**: OpenAI ChatKit Python SDK in custom-server mode (AegisChatKitServer with SSE)
- **First-Flow Testing**: mock-worker container publishes deterministic NATS events to validate ChatKit streaming without LLMs
- **Events**: NATS JetStream for worker separation (Phase 10)
- **Workspace**: Docker container isolation
- **Testing**: ginkgo (Go), pytest (Python), Playwright (E2E)
- **Code quality**: ruff + mypy (Python), golangci-lint (Go), ESLint (Angular)

## Implementation Order Summary

1. Phase 1: Go + Infrastructure foundation
2. Phase 2: Angular UI + Python ChatKit (combined)
3. Phase 3: LangGraph workflow skeleton with fake nodes
4. Phase 4: Skills and read-only agents
5. Phase 5: Workspace isolation
6. Phase 6: Implementation agents
7. Phase 7: Testing, review, verification
8. Phase 8: Human approval
9. Phase 9: Activity and artifact UX
10. Phase 10: NATS worker separation
11. Phase 11: Hardening and evaluation
