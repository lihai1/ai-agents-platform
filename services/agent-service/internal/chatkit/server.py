"""AegisChatKitServer — bridges ChatKit SDK with NATS-based agent workers.

respond() now yields typed ThreadStreamEvent objects (not raw SSE strings).
The SDK's process() method handles SSE serialization, thread/item persistence,
and request routing automatically.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ClientEffectEvent,
    ProgressUpdateEvent,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)

from internal.chatkit.context import RequestContext
from internal.chatkit.event_mapper import (
    _sanitize_terminal_data,
    final_answer_from_event,
    get_event_type,
    is_cancelled_event,
    is_completed_event,
    is_failed_event,
    progress_from_event,
    _payload,
)
from internal.chatkit.nats_bridge import NatsBridge

logger = logging.getLogger(__name__)

# How long to wait for events before starting the stream (seconds)
_INITIAL_DRAIN_DELAY = 0.3


def extract_text(input_message: UserMessageItem | None) -> str:
    """Extract plain text from a ChatKit UserMessageItem."""
    if input_message is None:
        return ""

    content = getattr(input_message, "content", None)

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
            else:
                text = getattr(part, "text", None)
            if text:
                parts.append(str(text))
        return "\n".join(parts).strip()

    return str(content or "").strip()


class AegisChatKitServer(ChatKitServer[RequestContext]):
    """ChatKit server that delegates agent execution to NATS-connected workers."""

    def __init__(self, store: Any, nats_bridge: NatsBridge):
        super().__init__(store=store)
        self.nats = nats_bridge

    # ------------------------------------------------------------------
    # ChatKit SDK contract: respond() yields ThreadStreamEvent objects
    # ------------------------------------------------------------------

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: RequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Stream agent events as typed ThreadStreamEvent objects.

        The SDK's process() method calls this and handles:
        - SSE serialization
        - Thread/item persistence via Store
        - Request deserialization
        """
        prompt = extract_text(input_user_message)
        run_id = context.run_id or thread.id

        logger.info("respond() called: thread=%s, run_id=%s", thread.id, run_id)

        # Handle empty prompt (structured-input continuation)
        if not prompt:
            yield ProgressUpdateEvent(icon="info", text="Continuing conversation...")
            await self.nats.nats.publish_chat_event(
                event_type="user_input",
                run_id=run_id,
                payload={"type": "user_input", "input": ""},
                user_id=context.user_subject,
            )
        elif context.is_new_thread:
            yield ProgressUpdateEvent(icon="agent", text=f"Agent started: {run_id}")
        else:
            yield ProgressUpdateEvent(icon="info", text="Continuing conversation...")
            await self.nats.nats.publish_chat_event(
                event_type="user_input",
                run_id=run_id,
                payload={"type": "user_input", "input": prompt},
                user_id=context.user_subject,
            )
            logger.info("Published user_input to existing agent run %s", run_id)

        # Acquire per-run event stream
        from internal.event_streams import get_event_stream
        event_stream = await get_event_stream(run_id)

        # Drain events buffered during startup
        async for event in self._drain_and_stream(event_stream, thread, context):
            yield event

    # ------------------------------------------------------------------
    # Internal: stream events from the per-run queue
    # ------------------------------------------------------------------

    async def _map_event_safe(
        self,
        event: dict,
        thread: ThreadMetadata,
        context: RequestContext,
    ) -> tuple[ThreadStreamEvent | None, bool]:
        """Map a worker event, swallowing mapping errors so the SSE stream survives bad events."""
        try:
            return self._map_worker_event(event, thread, context)
        except Exception as exc:
            logger.exception("Failed to map worker event: %s", exc)
            return (None, False)

    async def _drain_and_stream(
        self,
        event_stream: asyncio.Queue,
        thread: ThreadMetadata,
        context: RequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Drain initial queue then stream until a terminal event."""
        try:
            await asyncio.sleep(_INITIAL_DRAIN_DELAY)

            # Drain anything that arrived during the delay
            while not event_stream.empty():
                try:
                    event = event_stream.get_nowait()
                except asyncio.QueueEmpty:
                    break
                stream_event, is_terminal = await self._map_event_safe(
                    event, thread, context
                )
                if stream_event is not None:
                    yield stream_event
                if is_terminal:
                    return

            # Continuous stream
            while True:
                event = await event_stream.get()
                logger.debug("Event received: %s", event.get("event_type"))
                stream_event, is_terminal = await self._map_event_safe(
                    event, thread, context
                )
                if stream_event is not None:
                    yield stream_event
                if is_terminal:
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Streaming event loop failed: %s", exc)
            yield self._make_assistant_done_event(
                thread, context, f"Stream error: {exc}"
            )

    # ------------------------------------------------------------------
    # Event mapping: worker dict → ThreadStreamEvent
    # ------------------------------------------------------------------

    def _map_worker_event(
        self,
        event: dict,
        thread: ThreadMetadata,
        context: RequestContext,
    ) -> tuple[ThreadStreamEvent | None, bool]:
        """Map a raw worker event dict to a typed ThreadStreamEvent.

        Returns (event_or_none, is_terminal).
        """
        if is_completed_event(event):
            final_text = final_answer_from_event(event)
            payload = _payload(event)
            projects = payload.get("projects")
            done_event = self._make_assistant_done_event(thread, context, final_text, projects=projects)
            return (done_event, True)

        if is_failed_event(event):
            final_text = final_answer_from_event(event)
            done_event = self._make_assistant_done_event(thread, context, f"Agent failed: {final_text}")
            return (done_event, True)

        if is_cancelled_event(event):
            final_text = final_answer_from_event(event) or "Agent run was cancelled."
            done_event = self._make_assistant_done_event(thread, context, final_text)
            return (done_event, True)

        # Terminal output → ClientEffectEvent
        event_type = get_event_type(event)
        if event_type in ("terminal.started", "terminal.output", "terminal.input_required",
                          "terminal.completed", "terminal.failed", "terminal.cancelled"):
            payload = _payload(event)
            # Sanitize terminal data to remove cursor control sequences that cause messy display
            if "data" in payload and isinstance(payload["data"], str):
                payload["data"] = _sanitize_terminal_data(payload["data"])
            effect = ClientEffectEvent(name=event_type, data=payload)
            return (effect, False)

        # Structured UI events → ClientEffectEvent (preserves full payload)
        if event_type in ("waiting_input", "output"):
            payload = _payload(event)
            effect = ClientEffectEvent(name=event_type, data=payload)
            return (effect, False)

        # Default: progress
        progress = progress_from_event(event)
        if progress.text:
            return (progress, False)

        return (None, False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_assistant_done_event(
        self,
        thread: ThreadMetadata,
        context: RequestContext,
        text: str,
        *,
        projects: list | None = None,
    ) -> ThreadItemDoneEvent:
        """Build a ThreadItemDoneEvent wrapping an AssistantMessageItem."""
        item = AssistantMessageItem(
            thread_id=thread.id,
            id=self.store.generate_item_id("message", thread, context),
            created_at=datetime.now(timezone.utc),
            content=[AssistantMessageContent(text=text)],
        )
        event = ThreadItemDoneEvent(item=item)
        # Attach extra metadata for the Angular client
        event_dict = event.model_dump()
        event_dict["thread_id"] = thread.id
        if projects:
            event_dict["projects"] = projects
        return ThreadItemDoneEvent(**event_dict)
