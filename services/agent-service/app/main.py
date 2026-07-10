from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from internal.config import settings
from internal.db import connect, disconnect, get_session
from internal.chatkit import chatkit_router
from internal.messaging.nats import NATSMessaging
from internal.event_streams import push_event
from internal.handlers.nats import handle_agent_state_event, handle_worker_user_event
from internal.chatkit.router import nats_client, get_nats_client
from datetime import datetime, timezone
import os
import logging
import asyncio
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        service_id = os.getenv("SERVICE_ID", "agent-service")
        logger.info(f"Attempting to connect to NATS at {nats_url}")
        nats_client = NATSMessaging(nats_url=nats_url, service_id=service_id)
        logger.info("NATSMessaging instance created")
        await nats_client.connect()
        logger.info("NATS connection established")
        
        # Subscribe to all agent events for state updates
        # Using subscribe_to_events to listen to agent.events.> pattern
        await nats_client.subscribe_to_events(
            event_handler=lambda event: handle_agent_state_event(event, push_event),
            run_id=None  # Subscribe to all runs
        )
        
        # Subscribe to control-plane signals
        # Using subscribe_to_control to listen to agent.control.> pattern
        await nats_client.subscribe_to_control(
            control_handler=lambda event: handle_agent_state_event(event, push_event),
        )
        
        # Subscribe to worker output events (final_answer, progress_update)
        # Using subscribe_to_chat_events to listen to agent.chat.> pattern
        await nats_client.subscribe_to_chat_events(
            event_handler=lambda event: handle_worker_user_event(event, push_event),
            run_id=None  # Subscribe to all runs
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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"HTTP {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
    return response

app.include_router(chatkit_router, prefix="/api/chatkit", tags=["chatkit"])

@app.get("/healthz")
async def health():
    return {"status": "healthy"}

@app.get("/readyz")
async def ready():
    return {"status": "ready"}
