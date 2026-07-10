"""NATS message handlers for agent service"""
import logging

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
    if run_id and event_type in ["created", "preparing_workspace", "scouting", "planning", "designing", "implementing", "testing", "reviewing", "verifying", "completed", "failed", "final_answer", "progress_update"]:
        try:
            client = get_chatkit_client()
            
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
                "completed": "Task completed successfully",
                "failed": f"Task failed: {payload.get('error_message', 'Unknown error')}",
                "final_answer": payload.get("content", "Task completed"),
                "progress_update": payload.get("content", "Agent is working...")
            }
            
            message_content = message_map.get(event_type, f"Agent event: {event_type}")
            
            # Create ChatKit message via library (messaging infrastructure only)
            if client:
                client.chatkit.messages.create(
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
            
            message_content = payload.get("content", "")
            
            # Create ChatKit message via library (messaging infrastructure only)
            if client:
                client.chatkit.messages.create(
                    thread_id=run_id,
                    content=message_content,
                    role="assistant"
                )
                logger.info(f"Created ChatKit message for run {run_id} from worker: {message_content}")
            else:
                logger.warning(f"ChatKit client not available, skipping message creation for run {run_id}")
            
        except Exception as e:
            logger.error(f"Failed to create ChatKit message from worker: {e}")
