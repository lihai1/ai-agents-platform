from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from internal.db import get_session
from internal.models import ChatkitThread, ChatkitItem
from internal.agents.model_factory import get_model
from internal.workflow.router import CreateRunRequest
from internal.messaging.nats import NATSMessaging
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from typing import AsyncGenerator, Optional, Dict
import json
import httpx
import os
import uuid
import asyncio

chatkit_router = APIRouter()

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8080")
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# Global NATS client
nats_client: Optional[NATSMessaging] = None

# Store active chat event subscriptions
active_chat_subscriptions: Dict[str, bool] = {}

async def get_nats_client() -> NATSMessaging:
    """Get or create NATS client"""
    global nats_client
    if nats_client is None:
        nats_client = NATSMessaging(nats_url=NATS_URL)
        await nats_client.connect()
    return nats_client

async def subscribe_to_chat_events(chat_id: str) -> None:
    """Subscribe to agent events for a specific chat"""
    if chat_id in active_chat_subscriptions:
        return  # Already subscribed

    try:
        nats = await get_nats_client()
        await nats.subscribe_to_chat_events(
            chat_id=chat_id,
            event_handler=lambda event: handle_chat_event(chat_id, event)
        )
        active_chat_subscriptions[chat_id] = True
        print(f"Subscribed to agent events for chat {chat_id}")
    except Exception as e:
        print(f"Failed to subscribe to agent events for chat {chat_id}: {e}")

def handle_chat_event(chat_id: str, event: dict) -> None:
    """Handle incoming agent event from NATS"""
    print(f"[NATS RECEIVE] Received agent event for chat {chat_id}: {event}")
    # Events will be forwarded to UI via SSE through the existing event stream
    # The UI polls the SSE endpoint which reads from the database

class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    model_provider: str = "ollama"
    model_name: str = "llama3.2"
    trigger_workflow: bool = False
    project_id: Optional[str] = None
    repository_id: Optional[str] = None
    mock_mode: bool = False

async def create_chat_container(chat_id: str, repository_id: str, project_id: str, mock_mode: bool = False) -> bool:
    """Create a container for the chat via NATS message to control plane"""
    if mock_mode:
        print(f"Mock mode: Skipping container creation for chat {chat_id}")
        return True

    try:
        nats = await get_nats_client()
        await nats.publish_chat_start(
            chat_id=chat_id,
            repository_id=repository_id,
            project_id=project_id,
            mock_mode=mock_mode
        )
        print(f"Published chat start message for chat {chat_id}")
        return True
    except Exception as e:
        print(f"Failed to publish chat start message: {e}")
        return False

async def trigger_agent_worker(chat_id: str, user_id: str, project_id: str, repository_id: str, task: str, chatkit_thread_id: str, max_repair_count: int = 2) -> bool:
    """Trigger the agent worker by publishing run.start command"""
    try:
        nats = await get_nats_client()
        await nats.publish_command(
            command_type="run.start",
            run_id=chat_id,  # chat_id = run_id
            chat_id=chat_id,
            payload={
                "user_id": user_id,
                "project_id": project_id,
                "repository_id": repository_id,
                "task": task,
                "chatkit_thread_id": chatkit_thread_id,
                "max_repair_count": max_repair_count,
            }
        )
        print(f"Published agent run start command for chat {chat_id}")
        return True
    except Exception as e:
        print(f"Failed to publish agent run start command: {e}")
        return False

@chatkit_router.post("/", response_model=None)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(lambda: None)
) -> StreamingResponse:
    # Mock mode - skip database operations
    thread_id = request.thread_id or f"mock-thread-{uuid.uuid4()}"
    
    # Create container if repository_id provided and workflow is triggered
    if request.repository_id and request.trigger_workflow:
        await create_chat_container(thread_id, request.repository_id, request.project_id or "", request.mock_mode)
        # Subscribe to agent events for this chat
        await subscribe_to_chat_events(thread_id)
    
    # Stream response
    async def generate_response() -> AsyncGenerator[str, None]:
        # Trigger workflow if requested
        if request.trigger_workflow and request.project_id and request.repository_id:
            try:
                # Trigger agent worker via NATS
                await trigger_agent_worker(
                    chat_id=thread_id,
                    user_id="demo-user",  # TODO: Get from JWT
                    project_id=request.project_id,
                    repository_id=request.repository_id,
                    task=request.message,
                    chatkit_thread_id=thread_id,
                    max_repair_count=2
                )
                yield f"data: {json.dumps({'content': 'Workflow started. Processing your request...', 'thread_id': thread_id, 'workflow_triggered': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'content': f'Error triggering workflow: {str(e)}. Using chat response instead.', 'thread_id': thread_id, 'workflow_triggered': False})}\n\n"
        
        # Mock response since we don't have actual LLM running
        mock_response = f"Mock mode response: I received your message '{request.message}'. In mock mode, I skip actual LLM calls and return this predefined response. Container creation was {'skipped' if request.mock_mode else 'attempted'}."
        for i in range(0, len(mock_response), 10):
            chunk = mock_response[i:i+10]
            yield f"data: {json.dumps({'content': chunk, 'thread_id': thread_id})}\n\n"
            await asyncio.sleep(0.1)
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@chatkit_router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(ChatkitThread).where(ChatkitThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Get items
    items_result = await session.execute(
        select(ChatkitItem).where(ChatkitItem.thread_id == thread_id).order_by(ChatkitItem.created_at)
    )
    items = items_result.scalars().all()
    
    return {
        "thread": {
            "id": thread.id,
            "title": thread.title,
            "created_at": thread.created_at
        },
        "items": [
            {"id": item.id, "role": item.role, "content": item.content, "created_at": item.created_at}
            for item in items
        ]
    }


@chatkit_router.post("/close/{thread_id}")
async def close_chat(
    thread_id: str,
):
    """Close a chat and terminate its container"""
    try:
        nats = await get_nats_client()
        await nats.publish_chat_close(chat_id=thread_id)
        return {"status": "closed", "chat_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close chat: {str(e)}")
