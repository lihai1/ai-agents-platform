"""Event payload builders for the CrewAI worker.

Includes legacy event builders (state_*, chat_*) and new semantic terminal
event builders that use NATS payload-safe chunking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from agentic_shared.chunking import build_chunked_terminal_output_events
from agentic_shared.terminal_events import (
    terminal_cancelled,
    terminal_completed,
    terminal_failed,
    terminal_input_required,
    terminal_output,
    terminal_running,
    terminal_started,
    workflow_progress,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _message_id() -> str:
    return str(uuid.uuid4())


def base_event(
    event_type: str,
    run_id: str,
    payload: dict[str, Any],
    user_id: str,
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build a message using the existing platform envelope."""
    return {
        "message_id": message_id or _message_id(),
        "event_type": event_type,
        "run_id": run_id,
        "payload": payload,
        "timestamp": _now(),
        "schema_version": "1.0",
    }


def state_started(
    run_id: str,
    user_id: str,
    folder: str,
    resolved_folder: str,
    command: str,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return base_event(
        event_type="started",
        run_id=run_id,
        payload={
            "status": "started",
            "folder": folder,
            "resolved_folder": resolved_folder,
            "command": command,
        },
        user_id=user_id,
        session_id=session_id,
    )


def state_output(
    run_id: str,
    user_id: str,
    data: str,
    stream: str = "stdout",
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return base_event(
        event_type="output",
        run_id=run_id,
        payload={
            "status": "output",
            "stream": stream,
            "data": data,
        },
        user_id=user_id,
        session_id=session_id,
    )


def state_waiting_input(
    run_id: str,
    user_id: str,
    prompt: str,
    reason: str = "process_idle",
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return base_event(
        event_type="waiting_input",
        run_id=run_id,
        payload={
            "status": "waiting_input",
            "reason": reason,
            "prompt": prompt,
        },
        user_id=user_id,
        session_id=session_id,
    )


def state_completed(
    run_id: str,
    user_id: str,
    exit_code: int = 0,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return base_event(
        event_type="completed",
        run_id=run_id,
        payload={
            "status": "completed",
            "exit_code": exit_code,
        },
        user_id=user_id,
        session_id=session_id,
    )


def state_failed(
    run_id: str,
    user_id: str,
    error: str,
    reason: str = "process_error",
    exit_code: Optional[int] = None,
    candidates: Optional[list[str]] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "reason": reason,
        "error": error,
    }
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if candidates is not None:
        payload["candidates"] = candidates
    return base_event(
        event_type="failed",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
        session_id=session_id,
    )


def state_cancelled(
    run_id: str,
    user_id: str,
    reason: str = "control_close_received",
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return base_event(
        event_type="cancelled",
        run_id=run_id,
        payload={
            "status": "cancelled",
            "reason": reason,
        },
        user_id=user_id,
        session_id=session_id,
    )


def chat_progress(
    run_id: str,
    user_id: str,
    message: str,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    return base_event(
        event_type="progress_update",
        run_id=run_id,
        payload={"message": message},
        user_id=user_id,
        session_id=session_id,
    )


def chat_final(
    run_id: str,
    user_id: str,
    content: str,
    status: str = "completed",
    error: bool = False,
    session_id: Optional[str] = None,
    projects: Optional[list] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "content": content,
        "status": status,
        "error": error,
    }
    if projects is not None:
        payload["projects"] = projects
    return base_event(
        event_type="final_answer",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
        session_id=session_id,
    )


# ------------------------------------------------------------------
# Semantic terminal events (wrap shared builders in platform envelope)
# ------------------------------------------------------------------


def semantic_terminal_started(
    run_id: str,
    user_id: str,
    terminal_session_id: str,
    execution_id: str,
    sequence: int,
    command: str,
) -> dict[str, Any]:
    """Build envelope for terminal.started."""
    payload = terminal_started(
        run_id=run_id,
        terminal_session_id=terminal_session_id,
        execution_id=execution_id,
        sequence=sequence,
        command=command,
    )
    return base_event(
        event_type="terminal.started",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
    )


def semantic_terminal_output_chunked(
    run_id: str,
    user_id: str,
    terminal_session_id: str,
    sequence: int,
    data: str,
    max_chunk_bytes: int,
) -> list[dict[str, Any]]:
    """Build envelope(s) for terminal.output with payload-safe chunking.

    Returns a list of enveloped events (one per chunk).
    """
    chunk_events = build_chunked_terminal_output_events(
        run_id=run_id,
        terminal_session_id=terminal_session_id,
        sequence=sequence,
        data=data,
        max_chunk_bytes=max_chunk_bytes,
    )
    return [
        base_event(
            event_type="terminal.output",
            run_id=run_id,
            payload=chunk_payload,
            user_id=user_id,
        )
        for chunk_payload in chunk_events
    ]


def semantic_terminal_input_required(
    run_id: str,
    user_id: str,
    terminal_session_id: str,
    request_id: str,
    sequence: int,
    prompt: str = "",
    options: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build envelope for terminal.input_required."""
    payload = terminal_input_required(
        run_id=run_id,
        terminal_session_id=terminal_session_id,
        request_id=request_id,
        sequence=sequence,
        prompt=prompt,
        options=options,
    )
    return base_event(
        event_type="terminal.input_required",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
    )


def semantic_terminal_completed(
    run_id: str,
    user_id: str,
    terminal_session_id: str,
    sequence: int,
    exit_code: int,
) -> dict[str, Any]:
    """Build envelope for terminal.completed."""
    payload = terminal_completed(
        run_id=run_id,
        terminal_session_id=terminal_session_id,
        sequence=sequence,
        exit_code=exit_code,
    )
    return base_event(
        event_type="terminal.completed",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
    )


def semantic_terminal_failed(
    run_id: str,
    user_id: str,
    terminal_session_id: str,
    sequence: int,
    exit_code: Optional[int] = None,
    error: str = "",
) -> dict[str, Any]:
    """Build envelope for terminal.failed."""
    payload = terminal_failed(
        run_id=run_id,
        terminal_session_id=terminal_session_id,
        sequence=sequence,
        exit_code=exit_code,
        error=error,
    )
    return base_event(
        event_type="terminal.failed",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
    )


def semantic_terminal_cancelled(
    run_id: str,
    user_id: str,
    terminal_session_id: str,
    sequence: int,
    reason: str = "user_cancelled",
) -> dict[str, Any]:
    """Build envelope for terminal.cancelled."""
    payload = terminal_cancelled(
        run_id=run_id,
        terminal_session_id=terminal_session_id,
        sequence=sequence,
        reason=reason,
    )
    return base_event(
        event_type="terminal.cancelled",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
    )


def semantic_workflow_progress(
    run_id: str,
    user_id: str,
    sequence: int,
    graph_node: str,
    status: str,
    message: str = "",
) -> dict[str, Any]:
    """Build envelope for workflow.progress."""
    payload = workflow_progress(
        run_id=run_id,
        sequence=sequence,
        graph_node=graph_node,
        status=status,
        message=message,
    )
    return base_event(
        event_type="workflow.progress",
        run_id=run_id,
        payload=payload,
        user_id=user_id,
    )
