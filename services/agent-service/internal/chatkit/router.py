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
from internal.config import settings
from typing import Optional
import uuid
import json
import httpx
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

chatkit_router = APIRouter()

# Global NATS client
nats_client: Optional[NATSMessaging] = None
chatkit_server: Optional[AegisChatKitServer] = None


async def get_nats_client() -> NATSMessaging:
    """Get or create NATS client"""
    global nats_client
    if nats_client is None:
        nats_client = NATSMessaging(nats_url=settings.nats_url)
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


async def persist_run_id_to_project(project_id: str, run_id: str) -> bool:
    """Persist run_id to project record in control-plane"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{settings.control_plane_url}/api/v1/projects?id={project_id}",
                json={"thread_id": run_id}
            )
            response.raise_for_status()
        logger.info(f"Persisted run_id {run_id} to project {project_id}")
        return True
    except httpx.HTTPError as e:
        logger.error(f"Failed to persist run_id to project {project_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error persisting run_id to project {project_id}: {e}")
        return False


async def get_project_run_id(project_id: str) -> Optional[str]:
    """Get run_id from project record in control-plane"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.control_plane_url}/api/v1/projects?id={project_id}"
            )
            response.raise_for_status()
            project = response.json()
            return project.get("thread_id")
    except httpx.HTTPError as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting project {project_id}: {e}")
        return None


@chatkit_router.post("/")
async def chatkit_endpoint(request: Request):
    """ChatKit endpoint for streaming responses"""
    logger.info("ChatKit endpoint: POST request received")
    body = await request.body()
    logger.debug(f"ChatKit endpoint: Request body: {body}")
    base_context = context_from_request(request)
    ui_request = json.loads(body) if body else {}
    
    # Convert UI format to ChatKit protocol format
    from chatkit.types import ThreadMetadata, UserMessageItem
    
    try:
        ui_request = json.loads(body)
        
        # Extract run_id and message
        run_id = ui_request.get("thread_id") or ui_request.get("run_id")
        message = ui_request.get("message", "")
        
        logger.info(f"Run ID: {run_id}, Message: {message}")
        
        # Ensure run exists in store
        server = await get_chatkit_server()
        existing_run = await server.store.get_thread(run_id) if run_id else None
        is_new_thread = not existing_run
        
        if not existing_run:
            # Generate new run_id for new thread
            run_id = f"run-{uuid.uuid4()}"
            await server.store.create_thread({
                "id": run_id,
                "run_id": run_id,
                "user_subject": base_context.user_subject,
                "project_id": ui_request.get("project_id"),
                "repository_id": ui_request.get("repository_id"),
                "task": message,
            })
            logger.info(f"Created new run {run_id}")
            
            # Persist run_id to project record if project_id is available
            if ui_request.get("project_id"):
                await persist_run_id_to_project(ui_request.get("project_id"), run_id)
        else:
            # Retrieve existing run_id
            run_id = existing_run.get("run_id") or run_id
            logger.info(f"Reusing existing run {run_id}")
        
        context = RequestContext(
            user_subject=base_context.user_subject,
            org_id=base_context.org_id,
            request_id=base_context.request_id,
            authorization=base_context.authorization,
            project_id=ui_request.get("project_id"),
            repository_id=ui_request.get("repository_id"),
            run_id=run_id,
            mock_mode=bool(ui_request.get("mock_mode", False)),
            llm_provider=ui_request.get("llm_provider", base_context.llm_provider),
            model_name=ui_request.get("model_name", base_context.model_name),
            agent_type=ui_request.get("agent_type", base_context.agent_type),
            api_key=ui_request.get("api_key", base_context.api_key),
        )
        
        logger.debug(f"ChatKit endpoint called with context: project_id={context.project_id}, run_id={context.run_id}")
        
        # Create thread metadata
        thread = ThreadMetadata(
            id=run_id,
            title=message[:50] if message else "New Chat",
            created_at=datetime.now(timezone.utc),
        )
        
        # Create user message item with correct content format
        user_message = UserMessageItem(
            thread_id=run_id,
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            content=[{"type": "input_text", "text": message}],
            inference_options={},
        )
        
        logger.debug(f"User message created: {user_message}")
        
        # Call server.respond() with is_new_thread flag
        logger.debug("Calling server.respond...")
        event_stream = server.respond(thread, user_message, context, is_new_thread=is_new_thread)
        logger.debug("Event stream created")
        
        logger.info("Returning streaming response")
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
        )
        
    except Exception as e:
        logger.error(f"ChatKit server error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ChatKit server error: {str(e)}")


@chatkit_router.get("/threads/{run_id}")
async def get_thread(
    run_id: str = None,
    project_id: str = None,
    session: AsyncSession = Depends(get_session)
):
    """Get thread by run_id OR by project_id"""
    try:
        from internal.chatkit.store import PostgreSQLStore
        from internal.db import AsyncSessionLocal
        
        store = PostgreSQLStore(AsyncSessionLocal)
        
        # If project_id is provided, query control-plane for run_id
        if project_id:
            logger.info(f"Querying run by project_id: {project_id}")
            run_id = await get_project_run_id(project_id)
            if run_id:
                logger.info(f"Found run_id {run_id} for project {project_id}")
            else:
                # No run_id exists yet, return empty thread
                logger.info(f"No run_id found for project {project_id}")
                return {
                    "thread": None,
                    "items": []
                }
        
        # Now get thread by run_id
        if not run_id:
            raise HTTPException(status_code=400, detail="Either run_id or project_id required")
        
        logger.info(f"Fetching thread: {run_id}")
        thread = await store.get_thread(run_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread not found: {run_id}")
        
        messages = await store.get_messages(run_id)
        
        return {
            "thread": thread,
            "items": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get thread: {str(e)}")


@chatkit_router.post("/close/{run_id}")
async def close_chat(
    run_id: str,
    request: Request
):
    """Close a chat and terminate its container"""
    try:
        logger.info(f"Closing chat: {run_id}")
        
        # Publish chat close via NATS for workflow orchestration
        nats = await get_nats_client()
        await nats.publish_chat_close(run_id=run_id)
        logger.info(f"Published chat close for run_id: {run_id}")
        
        # Persist run_id to project record if project_id is available
        base_context = context_from_request(request)
        project_id = base_context.project_id
        if project_id:
            await persist_run_id_to_project(project_id, run_id)
        
        return {"status": "closed", "run_id": run_id}
    except Exception as e:
        logger.error(f"Failed to close chat {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to close chat: {str(e)}")


@chatkit_router.post("/input/{run_id}")
async def send_input(
    run_id: str,
    request: Request,
):
    """Send user input to a running worker (e.g. during a waiting_input prompt)."""
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
        user_input = data.get("input") or data.get("text") or data.get("content")
        if not user_input:
            raise HTTPException(status_code=400, detail="input is required")

        nats = await get_nats_client()
        user_subject = request.state.context.user_subject if hasattr(request.state, "context") else ""
        user_subject = user_subject.replace(":", "-") or "unknown"
        await nats.publish_chat_event(
            event_type="user_input",
            run_id=run_id,
            payload={"type": "user_input", "input": user_input},
            user_id=user_subject,
        )
        return {"status": "sent", "run_id": run_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send input: {str(e)}")
