"""Semantic terminal event builders for worker → service communication.

These replace the generic state_output / chat_progress events with structured,
typed payloads that the ChatKit server can map directly to ClientEffectEvent objects.
"""

from __future__ import annotations

import uuid
from typing import Any


def _event_id() -> str:
    return f"tevt-{uuid.uuid4()}"


def terminal_started(
    *,
    run_id: str,
    terminal_session_id: str,
    execution_id: str,
    sequence: int,
    command: str,
    status: str = "running",
) -> dict[str, Any]:
    """Build a terminal.started event payload."""
    return {
        "event_type": "terminal.started",
        "event_id": _event_id(),
        "run_id": run_id,
        "terminal_session_id": terminal_session_id,
        "execution_id": execution_id,
        "sequence": sequence,
        "command": command,
        "status": status,
    }


def terminal_output(
    *,
    run_id: str,
    terminal_session_id: str,
    output_id: str,
    sequence: int,
    chunk_index: int,
    chunk_count: int,
    is_final_chunk: bool,
    data: str,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Build a terminal.output event payload (single chunk)."""
    return {
        "event_type": "terminal.output",
        "event_id": _event_id(),
        "run_id": run_id,
        "terminal_session_id": terminal_session_id,
        "output_id": output_id,
        "sequence": sequence,
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "is_final_chunk": is_final_chunk,
        "encoding": encoding,
        "data": data,
    }


def terminal_input_required(
    *,
    run_id: str,
    terminal_session_id: str,
    request_id: str,
    sequence: int,
    input_type: str = "text",
    prompt: str = "",
    options: list[str] | None = None,
) -> dict[str, Any]:
    """Build a terminal.input_required event payload."""
    payload: dict[str, Any] = {
        "event_type": "terminal.input_required",
        "event_id": _event_id(),
        "run_id": run_id,
        "terminal_session_id": terminal_session_id,
        "request_id": request_id,
        "sequence": sequence,
        "input_type": input_type,
        "prompt": prompt,
    }
    if options:
        payload["options"] = options
    return payload


def terminal_running(
    *,
    run_id: str,
    terminal_session_id: str,
    sequence: int,
) -> dict[str, Any]:
    """Build a terminal.running event payload (after input received)."""
    return {
        "event_type": "terminal.running",
        "event_id": _event_id(),
        "run_id": run_id,
        "terminal_session_id": terminal_session_id,
        "sequence": sequence,
    }


def terminal_completed(
    *,
    run_id: str,
    terminal_session_id: str,
    sequence: int,
    exit_code: int,
) -> dict[str, Any]:
    """Build a terminal.completed event payload."""
    return {
        "event_type": "terminal.completed",
        "event_id": _event_id(),
        "run_id": run_id,
        "terminal_session_id": terminal_session_id,
        "sequence": sequence,
        "exit_code": exit_code,
    }


def terminal_failed(
    *,
    run_id: str,
    terminal_session_id: str,
    sequence: int,
    exit_code: int | None = None,
    error: str = "",
) -> dict[str, Any]:
    """Build a terminal.failed event payload."""
    return {
        "event_type": "terminal.failed",
        "event_id": _event_id(),
        "run_id": run_id,
        "terminal_session_id": terminal_session_id,
        "sequence": sequence,
        "exit_code": exit_code,
        "error": error,
    }


def terminal_cancelled(
    *,
    run_id: str,
    terminal_session_id: str,
    sequence: int,
    reason: str = "user_cancelled",
) -> dict[str, Any]:
    """Build a terminal.cancelled event payload."""
    return {
        "event_type": "terminal.cancelled",
        "event_id": _event_id(),
        "run_id": run_id,
        "terminal_session_id": terminal_session_id,
        "sequence": sequence,
        "reason": reason,
    }


def workflow_progress(
    *,
    run_id: str,
    sequence: int,
    graph_node: str,
    status: str,
    message: str = "",
) -> dict[str, Any]:
    """Build a workflow.progress event payload."""
    return {
        "event_type": "workflow.progress",
        "event_id": _event_id(),
        "run_id": run_id,
        "sequence": sequence,
        "graph_node": graph_node,
        "status": status,
        "message": message,
    }


def workflow_input_required(
    *,
    run_id: str,
    graph_node: str,
    request_id: str,
    interrupt_id: str,
    input_type: str,
    prompt: str,
    options: list[str] | None = None,
) -> dict[str, Any]:
    """Build a workflow.input_required event payload."""
    payload: dict[str, Any] = {
        "event_type": "workflow.input_required",
        "event_id": _event_id(),
        "run_id": run_id,
        "graph_node": graph_node,
        "request_id": request_id,
        "interrupt_id": interrupt_id,
        "input_type": input_type,
        "prompt": prompt,
    }
    if options:
        payload["options"] = options
    return payload
