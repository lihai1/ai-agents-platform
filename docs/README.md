# Architecture Diagrams

This directory contains UML and sequence diagrams for the SWE-1.6 Agentic Engineering Platform.

## Component Diagram

- **`architecture-component-diagram.mmd`** - High-level system architecture showing all components and their interactions
  - Client Layer (Angular Web UI)
  - API Layer (Go Control Plane, Python Agent API)
  - Worker Layer (Python Agent Worker)
  - Messaging Layer (NATS JetStream)
  - Data Layer (PostgreSQL, LangSmith)
  - Execution Layer (Docker Workspaces)
  - External Services (OpenAI, Anthropic, Ollama)

## Sequence Diagrams

### Core Flows

- **`sequence-chat-lifecycle.mmd`** - Complete chat lifecycle flow
  - User starts chat from UI with optional GitHub repository
  - Python service publishes NATS chat.start message
  - Control plane creates agent container via NATS
  - Orchestrator agent executes sequence of specialist agents
  - Each agent publishes state updates via NATS
  - Python service updates chat state and streams to UI
  - User observes events until human intervention requested
  - Chat termination via NATS chat.close message

- **`sequence-chatkit-chat.mmd`** - ChatKit chat interaction flow
  - User message through Angular UI
  - Thread creation/retrieval
  - LLM streaming response
  - Message persistence

- **`sequence-workflow-trigger.mmd`** - Workflow trigger and execution flow
  - ChatKit triggering agent workflow
  - NATS-based container creation
  - Worker execution initiation
  - LangGraph checkpoint persistence
  - Agent state updates via NATS

### Workflow Execution

- **`sequence-langgraph-workflow.mmd`** - Complete LangGraph workflow execution
  - State transitions through all phases
  - Specialist agent execution (SCOUTING, PLANNING, DESIGNING)
  - Parallel implementation agents
  - Validation agents (TESTING, REVIEWING, VERIFYING)
  - Repair loop handling
  - Workspace lifecycle

### Approval & Cancellation

- **`sequence-human-approval.mmd`** - Human approval workflow
  - Protected action detection
  - LangGraph interrupt for approval
  - Approval dialog in Angular UI
  - Approval/rejection handling
  - Workflow resumption

- **`sequence-cancellation.mmd`** - Run cancellation flow
  - User cancellation request
  - Cancellation flag propagation
  - Node boundary checks
  - Workspace cleanup
  - Terminal state handling

### Infrastructure

- **`sequence-event-streaming.mmd`** - Event streaming and SSE
  - SSE connection establishment
  - Event publication from LangGraph
  - NATS event streaming with chat-based subjects
  - PostgreSQL event persistence
  - Browser reconnection with Last-Event-ID
  - LangSmith tracing integration

- **`sequence-nats-messaging.mmd`** - NATS JetStream messaging
  - Chat start/close message publishing and consumption
  - Agent command publishing and consumption
  - Event publishing and consumption
  - Chat-based subject patterns (agent.chat.{chat_id}.{state})
  - Durable consumer setup
  - Idempotency handling
  - Dead letter queue
  - Worker recovery and message redelivery

## Viewing Diagrams

These diagrams are written in Mermaid format. You can view them using:

1. **GitHub/GitLab** - Native Mermaid rendering in markdown files
2. **VS Code** - Install the "Mermaid Preview" extension
3. **Online** - Use [Mermaid Live Editor](https://mermaid.live/)
4. **CLI** - Use `mmdc` (Mermaid CLI) to render to PNG/SVG

## Architecture Overview

The platform follows a microservices architecture:

- **Control Plane (Go)**: Manages users, organizations, projects, and repositories. Subscribes to NATS for chat lifecycle events (chat.start, chat.close) to manage agent containers.
- **Agent Service (Python)**: Handles ChatKit interactions and LangGraph workflows. Publishes NATS messages for chat start/close and subscribes to agent state events to update chat records.
- **Web UI (Angular)**: Provides user interface for chat and workflow monitoring.
- **NATS JetStream**: Provides reliable messaging between services. Uses chat-based subject patterns for per-chat routing.
- **PostgreSQL**: Persistent storage for application data, checkpoints, events, and chat containers.
- **Docker Workspaces**: Isolated execution environments for agent operations, managed by control plane via NATS.
- **LangGraph**: Orchestrates the multi-phase engineering workflow within agent containers.
- **LangSmith**: Distributed tracing for LLM operations.

## Key Design Patterns

- **NATS-Based Container Management**: Control plane subscribes to NATS chat.start/chat.close messages to manage agent containers instead of HTTP endpoints.
- **Chat-Based Subject Routing**: NATS subjects use chat-based patterns (agent.chat.{chat_id}.{state}) for per-chat message routing.
- **Worker Separation**: API and worker processes communicate via NATS for scalability.
- **Checkpoint Persistence**: LangGraph state persisted in PostgreSQL for recovery.
- **Event Streaming**: SSE for real-time UI updates with replay support.
- **Workspace Isolation**: Docker containers with resource limits for safe execution.
- **Human-in-the-Loop**: LangGraph interrupts for approval of sensitive operations.
- **Idempotency**: Message ID tracking to prevent duplicate processing.
- **Chat Lifecycle**: Complete lifecycle from chat start → container creation → agent execution → state updates → chat termination.
