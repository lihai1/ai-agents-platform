from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from internal.db import get_session
from internal.models import AgentRun
from internal.messaging.nats import NATSMessaging
from internal.chatkit.context import context_from_request, RequestContext
from internal.chatkit.server import AegisChatKitServer
from internal.chatkit.store import PostgreSQLStore
from internal.chatkit.nats_bridge import NatsBridge
from typing import Optional
import os
import uuid
import json
from datetime import datetime, timezone

chatkit_router = APIRouter()

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8080")
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# Global NATS client
nats_client: Optional[NATSMessaging] = None
chatkit_server: Optional[AegisChatKitServer] = None

async def get_nats_client() -> NATSMessaging:
    """Get or create NATS client"""
    global nats_client
    if nats_client is None:
        nats_client = NATSMessaging(nats_url=NATS_URL)
        await nats_client.connect()
    return nats_client

async def get_chatkit_server() -> AegisChatKitServer:
    """Get or create ChatKit server"""
    global chatkit_server
    if chatkit_server is None:
        from internal.db import AsyncSessionLocal
        # Ensure NATS client is initialized
        if nats_client is None:
            await get_nats_client()
        store = PostgreSQLStore(AsyncSessionLocal)
        nats_bridge = NatsBridge(nats_client)
        chatkit_server = AegisChatKitServer(store=store, nats_bridge=nats_bridge)
    return chatkit_server


@chatkit_router.post("/")
async def chatkit_endpoint(request: Request):
    """ChatKit endpoint for streaming responses"""
    print("ChatKit endpoint: POST request received")
    body = await request.body()
    print(f"ChatKit endpoint: Request body: {body}")
    base_context = context_from_request(request)
    ui_request = json.loads(body) if body else {}
    context = RequestContext(
        user_subject=base_context.user_subject,
        org_id=base_context.org_id,
        request_id=base_context.request_id,
        authorization=base_context.authorization,
        project_id=ui_request.get("project_id"),
        repository_id=ui_request.get("repository_id"),
        mock_mode=bool(ui_request.get("mock_mode", False)),
        llm_provider=ui_request.get("llm_provider", base_context.llm_provider),
        model_name=ui_request.get("model_name", base_context.model_name),
        agent_type=ui_request.get("agent_type", base_context.agent_type),
        api_key=ui_request.get("api_key", base_context.api_key),
    )
    
    print(f"ChatKit endpoint called, body: {body}")
    
    # Convert UI format to ChatKit protocol format
    from chatkit.types import ThreadMetadata, UserMessageItem
    
    try:
        ui_request = json.loads(body)
        
        # Extract thread_id and message
        thread_id = ui_request.get("thread_id") or f"thread-{uuid.uuid4()}"
        message = ui_request.get("message", "")
        
        print(f"Thread ID: {thread_id}, Message: {message}")
        
        # Ensure thread exists in store
        server = await get_chatkit_server()
        existing_thread = await server.store.get_thread(thread_id)
        if not existing_thread:
            await server.store.create_thread({
                "id": thread_id,
                "user_subject": base_context.user_subject,
                "project_id": context.project_id,
                "repository_id": context.repository_id,
                "task": message,
            })
            print(f"Created new thread in store: {thread_id}")
        
        # Create thread metadata
        thread = ThreadMetadata(
            id=thread_id,
            title=message[:50] if message else "New Chat",
            created_at=datetime.now(timezone.utc),
        )
        
        # Create user message item with correct content format
        user_message = UserMessageItem(
            thread_id=thread_id,
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            content=[{"type": "input_text", "text": message}],
            inference_options={},
        )
        
        print(f"User message created: {user_message}")
        
        # Call server.respond()
        print("Calling server.respond...")
        event_stream = server.respond(thread, user_message, context)
        print(f"Event stream created: {event_stream}")
        
        print("Returning streaming response")
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
        )
        
    except Exception as e:
        print(f"ChatKit server error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ChatKit server error: {str(e)}")


@chatkit_router.get("/threads/{run_id}")
async def get_thread(
    run_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get thread and messages from PostgreSQL store"""
    try:
        from internal.chatkit.store import PostgreSQLStore
        from internal.db import AsyncSessionLocal
        store = PostgreSQLStore(AsyncSessionLocal)
        
        thread = await store.get_thread(run_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread not found: {run_id}")
        
        messages = await store.get_messages(run_id)
        
        return {
            "thread": thread,
            "items": messages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get thread: {str(e)}")


@chatkit_router.post("/close/{run_id}")
async def close_chat(
    run_id: str,
):
    """Close a chat and terminate its container"""
    try:
        # Publish chat close via NATS for workflow orchestration
        nats = await get_nats_client()
        await nats.publish_chat_close(run_id=run_id)
        
        return {"status": "closed", "run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close chat: {str(e)}")
