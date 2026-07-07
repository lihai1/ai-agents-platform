from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from internal.config import settings
from internal.db import connect, disconnect
from internal.chatkit import chatkit_router
from internal.workflow.router import router as workflow_router
from internal.messaging.nats import NATSMessaging
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global NATS client
nats_client: NATSMessaging = None

async def handle_agent_state_event(event: dict) -> None:
    """Handle agent state events to update chat records"""
    chat_id = event.get("chat_id")
    event_type = event.get("event_type")
    payload = event.get("payload", {})
    
    logger.info(f"Received agent state event for chat {chat_id}: {event_type}")
    
    # TODO: Update chat state in database based on event
    # This would update the chat record with the current state
    # For now, just log the event
    logger.info(f"Chat {chat_id} state: {event_type}, payload: {payload}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global nats_client
    # Startup
    try:
        await connect()
    except Exception as e:
        print(f"Warning: Failed to connect to database: {e}")
        print("Continuing without database connection (mock mode)")
    
    # Connect to NATS
    try:
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        logger.info(f"Attempting to connect to NATS at {nats_url}")
        nats_client = NATSMessaging(nats_url=nats_url)
        logger.info("NATSMessaging instance created")
        await nats_client.connect()
        logger.info("NATS connection established")
        
        # Subscribe to all agent chat events for state updates
        # Using subscribe_to_events to listen to agent.chat.> pattern
        await nats_client.subscribe_to_events(
            event_handler=handle_agent_state_event,
            run_id=None  # Subscribe to all chats
        )
        
        logger.info("Connected to NATS and subscribed to agent state events")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.warning("Continuing without NATS connection")
        nats_client = None
    
    yield
    # Shutdown
    try:
        if nats_client:
            await nats_client.close()
    except Exception as e:
        logger.warning(f"Failed to close NATS connection: {e}")
    
    try:
        await disconnect()
    except Exception as e:
        print(f"Warning: Failed to disconnect from database: {e}")

app = FastAPI(
    title="Agent Service",
    description="AI agent service with ChatKit integration",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chatkit_router, prefix="/api/chatkit", tags=["chatkit"])
app.include_router(workflow_router, tags=["workflow"])

@app.get("/healthz")
async def health():
    return {"status": "healthy"}

@app.get("/readyz")
async def ready():
    return {"status": "ready"}
