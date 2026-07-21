"""ChatKit API router — handles agent orchestration and delegates to ChatKitServer."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internal.chatkit.context import context_from_request, RequestContext
from internal.chatkit.nats_bridge import NatsBridge
from internal.chatkit.server import AegisChatKitServer
from internal.chatkit.store import PostgreSQLStore
from internal.config import settings
from internal.db import AsyncSessionLocal, get_session
from internal.messaging.nats import NATSMessaging
from internal.models import AgentRun

logger = logging.getLogger(__name__)

chatkit_router = APIRouter()

# Global singletons (initialized lazily)
_nats_client: Optional[NATSMessaging] = None
_chatkit_server: Optional[AegisChatKitServer] = None


async def get_nats_client() -> NATSMessaging:
    """Get or create NATS client."""
    global _nats_client
    if _nats_client is None:
        _nats_client = NATSMessaging(nats_url=settings.nats_url)
        await _nats_client.connect()
    return _nats_client


async def get_chatkit_server() -> AegisChatKitServer:
    """Get or create ChatKit server singleton."""
    global _chatkit_server
    if _chatkit_server is None:
        nats = await get_nats_client()
        store = PostgreSQLStore(AsyncSessionLocal)
        nats_bridge = NatsBridge(nats)
        _chatkit_server = AegisChatKitServer(store=store, nats_bridge=nats_bridge)
    return _chatkit_server


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build_agent_metadata(context: RequestContext, ui_request: dict) -> dict:
    """Build metadata dictionary for agent start event."""
    return {
        "repository_id": context.repository_id,
        "project_id": context.project_id,
        "mock_mode": context.mock_mode,
        "agent_type": context.agent_type,
        "llm_provider": context.llm_provider,
        "model_name": context.model_name,
        "api_key": context.api_key,
        "max_tokens": 0,
        "max_cost": 0.0,
        "max_repair_count": 2,
    }


def _build_request_context(
    base_context: RequestContext,
    ui_request: dict,
    run_id: str | None,
    is_new_thread: bool = False,
) -> RequestContext:
    """Build RequestContext from base context and UI request."""
    return RequestContext(
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
        is_new_thread=is_new_thread,
    )


async def _create_or_reuse_thread(
    server: AegisChatKitServer,
    ui_request: dict,
    base_context: RequestContext,
    message: str,
) -> tuple[str, bool]:
    """Create new thread or reuse existing one. Returns (run_id, is_new_thread)."""
    run_id = ui_request.get("thread_id") or ui_request.get("run_id")

    if not run_id and ui_request.get("project_id"):
        thread = await server.store.get_thread_by_project_id(ui_request.get("project_id"))
        if thread:
            run_id = thread.get("run_id")
            logger.info("Found existing run_id %s from project %s", run_id, ui_request.get("project_id"))

    existing_run = await server.store.get_thread_legacy(run_id) if run_id else None
    is_new_thread = not existing_run

    if not existing_run:
        run_id = f"run-{uuid.uuid4()}"
        await server.store.create_thread_legacy({
            "id": run_id,
            "run_id": run_id,
            "user_subject": base_context.user_subject,
            "project_id": ui_request.get("project_id"),
            "repository_id": ui_request.get("repository_id"),
            "task": message,
        })
        logger.info("Created new run %s", run_id)
    else:
        run_id = existing_run.get("run_id") or run_id
        logger.info("Reusing existing run %s", run_id)

    return run_id, is_new_thread


def _is_standard_chatkit_request(body: bytes) -> bool:
    """Check if the body is a standard ChatKit SDK request (has 'type' field)."""
    try:
        parsed = json.loads(body)
        return isinstance(parsed, dict) and "type" in parsed
    except (json.JSONDecodeError, ValueError):
        return False


def _legacy_to_chatkit_request(ui_request: dict, thread_id: str) -> bytes:
    """Transform legacy UI request body into standard ChatKit threads.add_user_message."""
    message = ui_request.get("message", "")
    chatkit_req = {
        "type": "threads.add_user_message",
        "params": {
            "thread_id": thread_id,
            "input": {
                "content": [{"type": "input_text", "text": message}],
                "attachments": [],
                "inference_options": {},
            },
        },
    }
    return json.dumps(chatkit_req).encode("utf-8")


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@chatkit_router.post("/")
async def chatkit_endpoint(request: Request):
    """ChatKit endpoint — delegates to server.process() per SDK contract.

    Accepts both standard ChatKit SDK requests (with 'type' field) and legacy
    UI requests (with 'message' field) for backward compatibility during
    transition.
    """
    from chatkit.server import StreamingResult, NonStreamingResult

    body = await request.body()
    base_context = context_from_request(request)

    try:
        server = await get_chatkit_server()

        if _is_standard_chatkit_request(body):
            # Standard ChatKit SDK request — delegate directly to process()
            context = _build_request_context(base_context, {}, None)
            # Extract thread_id from request to set run_id on context
            parsed = json.loads(body)
            params = parsed.get("params", {})
            thread_id = params.get("thread_id")
            if thread_id:
                context = _build_request_context(base_context, {"run_id": thread_id}, thread_id)
        else:
            # Legacy UI request — create/reuse thread, publish agent start, transform
            ui_request = json.loads(body) if body else {}
            message = ui_request.get("message", "")

            run_id, is_new_thread = await _create_or_reuse_thread(
                server, ui_request, base_context, message
            )
            context = _build_request_context(base_context, ui_request, run_id, is_new_thread)

            # Publish agent start for new threads
            if is_new_thread:
                metadata = _build_agent_metadata(context, ui_request)
                await server.nats.publish_agent_start(
                    run_id=run_id,
                    conversation_id=run_id,
                    user_subject=context.user_subject,
                    prompt=message,
                    metadata=metadata,
                )
                logger.info("Agent start published for new thread %s", run_id)

            # Transform to standard ChatKit request
            body = _legacy_to_chatkit_request(ui_request, run_id)

        result = await server.process(body, context)

        if isinstance(result, StreamingResult):
            return StreamingResponse(
                result,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        if isinstance(result, NonStreamingResult):
            return Response(
                content=result.json,
                media_type="application/json",
            )

        raise RuntimeError(f"Unsupported ChatKit result: {type(result)!r}")

    except Exception as e:
        logger.error("ChatKit endpoint error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ChatKit server error: {str(e)}")


@chatkit_router.post("/start")
async def agent_start_endpoint(request: Request):
    """Agent start endpoint - starts agent worker without requiring a message"""
    logger.info("Agent start endpoint: POST request received")
    body = await request.body()
    logger.debug(f"Agent start endpoint: Request body: {body}")
    base_context = context_from_request(request)

    try:
        ui_request = json.loads(body) if body else {}

        server = await get_chatkit_server()
        run_id, is_new_thread = await _create_or_reuse_thread(
            server,
            ui_request,
            base_context,
            "new thread",
        )

        context = _build_request_context(base_context, ui_request, run_id)
        metadata = _build_agent_metadata(context, ui_request)
        metadata["project_path"] = ui_request.get("project_path")

        await server.nats.publish_agent_start(
            run_id=run_id,
            conversation_id=run_id,
            user_subject=context.user_subject,
            prompt="",
            metadata=metadata,
        )
        logger.info(f"Published agent start event for run {run_id} (new={is_new_thread})")

        return {"run_id": run_id, "status": "started", "is_new_thread": is_new_thread}

    except Exception as e:
        logger.error(f"Error in agent start endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # If project_id is provided, query local DB for run_id
        if project_id:
            logger.info(f"Querying run by project_id: {project_id}")
            thread = await store.get_thread_by_project_id(project_id)
            if thread:
                run_id = thread.get("run_id")
                logger.info(f"Found run_id {run_id} for project {project_id}")
            else:
                logger.info(f"No run_id found for project {project_id}")
                return {
                    "thread": None,
                    "items": []
                }
        
        if not run_id:
            raise HTTPException(status_code=400, detail="Either run_id or project_id required")
        
        logger.info(f"Fetching thread: {run_id}")
        thread = await store.get_thread_legacy(run_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread not found: {run_id}")
        
        return {
            "thread": thread,
            "items": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get thread: {str(e)}")


@chatkit_router.get("/threads/by-project/{project_id}")
async def get_thread_by_project(
    project_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get the latest thread for a project by project_id"""
    try:
        from internal.chatkit.store import PostgreSQLStore
        from internal.db import AsyncSessionLocal
        
        if not project_id or not project_id.strip():
            raise HTTPException(status_code=400, detail="project_id is required")
        
        store = PostgreSQLStore(AsyncSessionLocal)
        
        logger.info(f"Querying latest thread by project_id: {project_id}")
        thread = await store.get_thread_by_project_id(project_id)
        
        if not thread:
            logger.info(f"No thread found for project {project_id}")
            return {
                "thread": None,
                "items": []
            }
        
        run_id = thread.get("run_id")
        logger.info(f"Found run_id {run_id} for project {project_id}")
        
        return {
            "thread": thread,
            "items": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thread by project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get thread by project: {str(e)}")


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

        payload: dict[str, Any] = {"type": "user_input", "input": user_input}
        approval_request_id = data.get("approval_request_id")
        if approval_request_id:
            payload["approval_request_id"] = approval_request_id

        try:
            user_subject = context_from_request(request).user_subject
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AgentRun).where(AgentRun.id == run_id))
            run = result.scalar_one_or_none()

        if not run or run.user_id != user_subject:
            raise HTTPException(status_code=404, detail="User or run not found")

        nats = await get_nats_client()
        await nats.publish_chat_event(
            event_type="user_input",
            run_id=run_id,
            payload=payload,
            user_id=user_subject,
        )
        return {"status": "sent", "run_id": run_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send input: {str(e)}")
