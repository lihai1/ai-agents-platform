"""Integration test: semantic terminal events flow through event_streams to SSE."""
import asyncio
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from internal.event_streams import get_event_stream, push_event, remove_event_stream
from internal.handlers.nats import handle_agent_state_event


RUN_ID = f"terminal-test-{uuid.uuid4().hex[:8]}"
USER_ID = "test-user-terminal"


@pytest.fixture
async def event_stream():
    """Create and teardown an event stream for the test run."""
    stream = await get_event_stream(RUN_ID)
    yield stream
    await remove_event_stream(RUN_ID)


@pytest.mark.integration
async def test_terminal_started_forwarded_to_sse(event_stream):
    """terminal.started event is pushed to the SSE stream with correct payload."""
    event = {
        "run_id": RUN_ID,
        "event_type": "terminal.started",
        "payload": {
            "terminal_session_id": "tsess-abc123",
            "command": "uv run python -m stock_analysis.main",
            "sequence": 1,
        },
        "timestamp": "2026-07-20T00:00:00Z",
    }

    await handle_agent_state_event(event, push_event)

    msg = event_stream.get_nowait()
    assert msg["event_type"] == "terminal.started"
    assert msg["run_id"] == RUN_ID
    assert msg["payload"]["terminal_session_id"] == "tsess-abc123"
    assert msg["payload"]["command"] == "uv run python -m stock_analysis.main"
    assert msg["payload"]["sequence"] == 1


@pytest.mark.integration
async def test_terminal_output_forwarded_to_sse(event_stream):
    """terminal.output event with chunking metadata is forwarded intact."""
    event = {
        "run_id": RUN_ID,
        "event_type": "terminal.output",
        "payload": {
            "terminal_session_id": "tsess-abc123",
            "output_id": "out-001",
            "data": "Hello from CrewAI\n",
            "chunk_index": 0,
            "chunk_count": 1,
            "sequence": 2,
        },
        "timestamp": "2026-07-20T00:00:01Z",
    }

    await handle_agent_state_event(event, push_event)

    msg = event_stream.get_nowait()
    assert msg["event_type"] == "terminal.output"
    assert msg["payload"]["output_id"] == "out-001"
    assert msg["payload"]["data"] == "Hello from CrewAI\n"
    assert msg["payload"]["chunk_index"] == 0
    assert msg["payload"]["chunk_count"] == 1


@pytest.mark.integration
async def test_terminal_failed_forwarded_to_sse(event_stream):
    """terminal.failed event carries exit_code and reason."""
    event = {
        "run_id": RUN_ID,
        "event_type": "terminal.failed",
        "payload": {
            "terminal_session_id": "tsess-abc123",
            "exit_code": 1,
            "reason": "non_zero_exit",
            "sequence": 10,
        },
        "timestamp": "2026-07-20T00:00:10Z",
    }

    await handle_agent_state_event(event, push_event)

    msg = event_stream.get_nowait()
    assert msg["event_type"] == "terminal.failed"
    assert msg["payload"]["exit_code"] == 1
    assert msg["payload"]["reason"] == "non_zero_exit"


@pytest.mark.integration
async def test_terminal_completed_forwarded_to_sse(event_stream):
    """terminal.completed event carries exit_code 0."""
    event = {
        "run_id": RUN_ID,
        "event_type": "terminal.completed",
        "payload": {
            "terminal_session_id": "tsess-abc123",
            "exit_code": 0,
            "sequence": 10,
        },
        "timestamp": "2026-07-20T00:00:10Z",
    }

    await handle_agent_state_event(event, push_event)

    msg = event_stream.get_nowait()
    assert msg["event_type"] == "terminal.completed"
    assert msg["payload"]["exit_code"] == 0


@pytest.mark.integration
async def test_terminal_cancelled_forwarded_to_sse(event_stream):
    """terminal.cancelled event is forwarded."""
    event = {
        "run_id": RUN_ID,
        "event_type": "terminal.cancelled",
        "payload": {
            "terminal_session_id": "tsess-abc123",
            "reason": "user_cancelled",
            "sequence": 10,
        },
        "timestamp": "2026-07-20T00:00:10Z",
    }

    await handle_agent_state_event(event, push_event)

    msg = event_stream.get_nowait()
    assert msg["event_type"] == "terminal.cancelled"
    assert msg["payload"]["reason"] == "user_cancelled"


@pytest.mark.integration
async def test_terminal_events_preserve_ordering(event_stream):
    """Multiple terminal events arrive in FIFO order."""
    events = [
        {"run_id": RUN_ID, "event_type": "terminal.started", "payload": {"terminal_session_id": "tsess-order", "command": "echo hi", "sequence": 1}},
        {"run_id": RUN_ID, "event_type": "terminal.output", "payload": {"terminal_session_id": "tsess-order", "output_id": "o1", "data": "hi\n", "chunk_index": 0, "chunk_count": 1, "sequence": 2}},
        {"run_id": RUN_ID, "event_type": "terminal.completed", "payload": {"terminal_session_id": "tsess-order", "exit_code": 0, "sequence": 3}},
    ]

    for e in events:
        await handle_agent_state_event(e, push_event)

    received = []
    while not event_stream.empty():
        received.append(event_stream.get_nowait())

    assert len(received) == 3
    assert [r["event_type"] for r in received] == ["terminal.started", "terminal.output", "terminal.completed"]
