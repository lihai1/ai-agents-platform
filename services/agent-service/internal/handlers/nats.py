"""NATS message handlers for agent service"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Global ChatKit client for local agent-service
chatkit_client = None


class LocalChatKitClient:
    """Local ChatKit client for agent-service (custom ChatKit server)"""
    class Messages:
        def __init__(self, store):
            self.store = store
        
        async def create(self, thread_id: str, content: str, role: str):
            """Create message in local PostgreSQL store"""
            try:
                await self.store.add_message(thread_id, role, content)
                logger.info(f"Local ChatKit: Created message in PostgreSQL store for thread {thread_id}")
            except Exception as e:
                logger.error(f"Local ChatKit: Failed to create message: {e}")
    
    def __init__(self, store):
        self.store = store
        self.chatkit = type('ChatKit', (), {'messages': self.Messages(store)})()


def get_chatkit_client():
    """Get or create local ChatKit client"""
    global chatkit_client
    if chatkit_client is None:
        # agent-service acts as custom ChatKit server, always use local PostgreSQL store
        from internal.chatkit.store import PostgreSQLStore
        from internal.db import AsyncSessionLocal
        store = PostgreSQLStore(AsyncSessionLocal)
        chatkit_client = LocalChatKitClient(store)
        logger.info("Using local ChatKit client (agent-service as custom ChatKit server)")
    
    return chatkit_client


async def handle_agent_state_event(event: dict, push_event_func) -> None:
    """Handle agent state events and push to SSE streams"""
    run_id = event.get("run_id")
    event_type = event.get("event_type")
    payload = event.get("payload", {})

    logger.info(f"Received agent state event for run {run_id}: {event_type}")
    
    # Manage AgentStep lifecycle based on state events
    await _manage_agent_step_lifecycle(run_id, event_type, payload)
    
    # Push to SSE stream queue for real-time delivery
    if run_id:
        await push_event_func(run_id, {
            "event_type": event_type,
            "run_id": run_id,
            "payload": payload,
            "timestamp": event.get("timestamp")
        })
        logger.info(f"Pushed event to SSE stream for run {run_id}")
    
    # Create ChatKit message based on event type using ChatKit library
    if run_id and event_type in ["created", "preparing_workspace", "scouting", "planning", "designing", "implementing", "testing", "reviewing", "verifying", "waiting_input", "completed", "failed", "final_answer", "progress_update"]:
        try:
            client = get_chatkit_client()
            
            # Ensure AgentRun record exists for this run_id
            await _ensure_agent_run_exists(run_id, payload)
            
            # Map event types to user-friendly messages
            message_map = {
                "created": "Agent run started",
                "preparing_workspace": "Preparing workspace...",
                "scouting": "Scouting repository...",
                "planning": "Planning approach...",
                "designing": "Designing solution...",
                "implementing": "Implementing changes...",
                "testing": "Testing implementation...",
                "reviewing": "Reviewing changes...",
                "verifying": "Verifying solution...",
                "waiting_input": payload.get("prompt", "Waiting for your input..."),
                "completed": "Task completed successfully",
                "failed": f"Task failed: {payload.get('error_message', 'Unknown error')}",
                "final_answer": payload.get("content", "Task completed"),
                "progress_update": payload.get("content", "Agent is working...")
            }
            
            message_content = message_map.get(event_type, f"Agent event: {event_type}")
            
            # Create ChatKit message via library (messaging infrastructure only)
            if client:
                await client.chatkit.messages.create(
                    thread_id=run_id,
                    content=message_content,
                    role="assistant"
                )
                logger.info(f"Created ChatKit message for run {run_id}: {message_content}")
            else:
                logger.warning(f"ChatKit client not available, skipping message creation for run {run_id}")
            
        except Exception as e:
            logger.error(f"Failed to create ChatKit message: {e}")
    
    logger.info(f"Run {run_id} state: {event_type}, payload: {payload}")


async def handle_worker_user_event(event: dict, push_event_func) -> None:
    """Handle worker user events (final answers, progress) from agent.chat.{run_id}.user.events"""
    run_id = event.get("run_id")
    event_type = event.get("event_type")
    payload = event.get("payload", {})
    
    logger.info(f"Received worker user event for run {run_id}: {event_type}, payload: {payload}")
    
    # Push to SSE stream queue for real-time delivery
    if run_id:
        await push_event_func(run_id, {
            "event_type": event_type,
            "run_id": run_id,
            "payload": payload,
            "timestamp": event.get("timestamp")
        })
        logger.info(f"Pushed worker user event to SSE stream for run {run_id}")
    
    # Create ChatKit message for worker user events using ChatKit library
    if run_id and event_type in ["final_answer", "progress_update"]:
        try:
            client = get_chatkit_client()
            
            # Ensure AgentRun record exists for this run_id
            await _ensure_agent_run_exists(run_id, payload)
            
            message_content = payload.get("content", "")
            
            # Create ChatKit message via library (messaging infrastructure only)
            if client:
                await client.chatkit.messages.create(
                    thread_id=run_id,
                    content=message_content,
                    role="assistant"
                )
                logger.info(f"Created ChatKit message for run {run_id} from worker: {message_content}")
            else:
                logger.warning(f"ChatKit client not available, skipping message creation for run {run_id}")
            
        except Exception as e:
            logger.error(f"Failed to create ChatKit message from worker: {e}")


async def handle_agent_error(event: dict, push_event_func) -> None:
    """Handle error messages from agent-worker"""
    error_type = event.get("error_type")
    error_message = event.get("error_message")
    payload = event.get("payload", {})
    
    logger.error(f"Received agent error: {error_type} - {error_message}")
    
    # Push to SSE stream for real-time delivery (similar to handle_agent_state_event)
    await push_event_func("system", {
        "event_type": "error",
        "error_type": error_type,
        "error_message": error_message,
        "payload": payload,
        "timestamp": event.get("timestamp")
    })
    logger.info("Pushed error event to SSE stream")


async def _manage_agent_step_lifecycle(run_id: str, event_type: str, payload: dict) -> None:
    """Manage AgentStep lifecycle based on state events from agent-worker"""
    from internal.db import AsyncSessionLocal
    from internal.models import AgentStep
    from sqlalchemy import select
    
    # Map event types to phases and agent names
    phase_agent_map = {
        "preparing_workspace": ("PREPARING_WORKSPACE", "workspace-preparer"),
        "scouting": ("SCOUTING", "repo-scout"),
        "planning": ("PLANNING", "skills-lead"),
        "designing": ("DESIGNING", "solution-planner"),
        "implementing": ("IMPLEMENTING", "specialist-agents"),
        "testing": ("TESTING", "test-engineer"),
        "reviewing": ("REVIEWING", "code-reviewer"),
        "verifying": ("VERIFYING", "completion-verifier"),
        "repairing": ("REPAIRING", "repair-agent"),
        "waiting_approval": ("WAITING_APPROVAL", "approval-handler"),
        "waiting_input": ("WAITING_INPUT", "input-handler"),
        "reasoning": ("REASONING", "single-agent"),
    }
    
    if event_type not in phase_agent_map:
        return
    
    phase, agent_name = phase_agent_map[event_type]
    
    async with AsyncSessionLocal() as session:
        # Check if there's an existing step for this phase
        result = await session.execute(
            select(AgentStep).where(
                AgentStep.chat_id == run_id,
                AgentStep.phase == phase
            ).order_by(AgentStep.started_at.desc())
        )
        existing_step = result.scalar_one_or_none()
        
        if existing_step and existing_step.status == "started":
            # Complete the existing step
            existing_step.status = "completed"
            existing_step.output_data = payload
            existing_step.completed_at = datetime.now()
            await session.commit()
            logger.info(f"Completed AgentStep for run {run_id}, phase {phase}")
        elif not existing_step:
            # Create a new step
            step = AgentStep(
                chat_id=run_id,
                phase=phase,
                agent_name=agent_name,
                status="started",
                input_data=payload,
                started_at=datetime.now()
            )
            session.add(step)
            await session.commit()
            logger.info(f"Created AgentStep for run {run_id}, phase {phase}")


async def _ensure_agent_run_exists(run_id: str, payload: dict) -> None:
    """Ensure AgentRun record exists for the given run_id"""
    from internal.db import AsyncSessionLocal
    from internal.models import AgentRun
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        # Check if AgentRun exists
        result = await session.execute(
            select(AgentRun).where(AgentRun.id == run_id)
        )
        existing_run = result.scalar_one_or_none()
        
        if not existing_run:
            # Create AgentRun record for worker's run_id
            run = AgentRun(
                id=run_id,
                user_id=payload.get("user_id", "unknown"),
                project_id=payload.get("project_id", ""),
                repository_id=payload.get("repository_id", ""),
                task=payload.get("task", ""),
                status="RUNNING",
            )
            session.add(run)
            await session.commit()
            logger.info(f"Created AgentRun record for worker run_id: {run_id}")
        else:
            logger.debug(f"AgentRun record already exists for run_id: {run_id}")


async def handle_worker_ready(event: dict, push_event_func) -> None:
    """Handle worker ready signals and push progress update to SSE streams"""
    run_id = event.get("run_id")
    event_type = event.get("event_type")
    payload = event.get("payload", {})

    logger.info(f"Received worker ready signal for run {run_id}: {event_type}")

    # Push progress update to SSE stream
    if run_id:
        await push_event_func(run_id, {
            "type": "progress_update",
            "icon": "agent",
            "text": f"Agent started: {run_id}"
        })
        logger.info(f"Pushed progress update for worker ready: {run_id}")
