"""Full NATS/Postgres integration test for the CrewAI expert worker.

Drives the durable state machine through:
  container start → worker_ready → project selection → patch approval →
  dependency sync → CLI start → terminal state

Uses pytest-describe for readable step-by-step structure.
"""

from __future__ import annotations

import asyncio
import ast
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

import pytest

from helpers import WorkerTestHarness, sendNatsUserMessage

logger = logging.getLogger(__name__)

IMAGE = "agentic-agents-platform-agent-worker:latest"
NETWORK = os.environ.get("AGENT_WORKER_NETWORK", "agent-worker_default")
REPOSITORY_URL = "https://github.com/crewAIInc/crewAI-examples.git"
PROJECT_NAME = "stock_analysis"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _ensure_image() -> None:
    if _run(["docker", "image", "inspect", IMAGE]).returncode != 0:
        pytest.skip(f"Docker image {IMAGE} not found; run 'docker build' first")


def _start_container(run_id: str, user_id: str, container_name: str) -> str:
    """Start container and return its id."""
    logger.info("Starting container %s for run %s", container_name, run_id)
    _run(["docker", "rm", "-f", container_name])
    env_pairs = {
        "RUN_ID": run_id,
        "USER_ID": user_id,
        "NATS_URL": "nats://nats:4222",
        "DATABASE_URL": "postgresql+asyncpg://agentic:agentic@postgres:5432/agentic",
        "REPOSITORY_URL": REPOSITORY_URL,
        "BRANCH": "main",
        "AGENT_TYPE": "crewai-expert",
        "MOCK_MODE": "false",
        "CREWAI_EXPERT_REPAIR": "true",
        "CREWAI_EXPERT_REQUIRE_PATCH_APPROVAL": "true",
        "CREWAI_EXPERT_MAX_SELECTION_ATTEMPTS": "3",
        "CREWAI_EXPERT_MAX_PATCH_ATTEMPTS": "2",
        "COMMAND_TIMEOUT_SECONDS": "10",
        "CREWAI_EXPERT_SYNC_TIMEOUT_SECONDS": "120",
        "OLLAMA_BASE_URL": "http://0.0.0.0:1",
        "MODEL_NAME": "fake-model",
    }
    cmd = ["docker", "run", "-d", "--network", NETWORK, "--name", container_name]
    for k, v in env_pairs.items():
        cmd += ["-e", f"{k}={v}"]
    cmd.append(IMAGE)
    result = _run(cmd, check=True)
    container_id = result.stdout.strip()
    if not container_id:
        raise RuntimeError("docker run did not return a container id")
    logger.info("Container started: %s", container_id[:12])
    return container_id


def _stop_container(container_name: str) -> None:
    """Stop container, dump logs, remove."""
    logger.info("Stopping container %s", container_name)
    _run(["docker", "stop", "--time", "5", container_name])
    log_path = f"/tmp/crewai_int_{container_name}.log"
    try:
        logs = _run(["docker", "logs", container_name])
        Path(log_path).write_text(logs.stdout + logs.stderr, encoding="utf-8", errors="ignore")
        logger.info("Container logs → %s", log_path)
    except Exception as exc:
        logger.warning("Failed to capture container logs: %s", exc)
    _run(["docker", "rm", "-f", container_name])


async def _stream_container_logs(container_name: str) -> asyncio.Task:
    """Stream docker logs in background, emitting each line via logger."""

    async def _tail():
        proc = await asyncio.create_subprocess_exec(
            "docker", "logs", "-f", container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                logger.info("[container] %s", line.decode(errors="replace").rstrip())
        except asyncio.CancelledError:
            proc.terminate()
            raise

    return asyncio.create_task(_tail())


async def _wait_for_state(
    harness: WorkerTestHarness,
    *,
    event_type: Optional[str] = None,
    reason: Optional[str] = None,
    timeout: float = 120.0,
) -> Optional[dict[str, Any]]:
    """Poll harness state events until a matching event arrives."""
    logger.info("Waiting for state: type=%s reason=%s timeout=%ss", event_type, reason, timeout)
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        for ev in harness.events["state"]:
            data = ev["data"]
            if event_type and data.get("event_type") != event_type:
                continue
            payload = data.get("payload", {})
            if reason and payload.get("reason") != reason:
                continue
            logger.info("Matched state event: type=%s", data.get("event_type"))
            return data
        await asyncio.sleep(0.2)
    logger.warning("Timed out waiting for state: type=%s reason=%s", event_type, reason)
    return None


async def _wait_for_terminal_state(
    harness: WorkerTestHarness, timeout: float = 300.0
) -> Optional[str]:
    """Wait for completed/failed/cancelled and return the type."""
    terminal_types = {"completed", "failed", "cancelled"}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        for ev in harness.events["state"]:
            et = ev["data"].get("event_type")
            if et in terminal_types:
                logger.info("Terminal state received: %s", et)
                return str(et)
        await asyncio.sleep(0.2)
    logger.warning("Timed out waiting for terminal state")
    return None


async def _send_input(nats_client, run_id: str, user_id: str, text: str) -> None:
    logger.info("Sending user input: %r", text)
    await sendNatsUserMessage(
        nats_client, run_id, user_id,
        {"type": "user_input", "payload": {"input": text}},
    )


def _parse_approval_options(event: dict[str, Any]) -> dict[str, Any]:
    """Extract approval dict from the prompt field."""
    prompt = event.get("payload", {}).get("prompt", "")
    try:
        return ast.literal_eval(prompt)
    except (ValueError, SyntaxError):
        return {}


def _get_terminal_chat_events(harness: WorkerTestHarness) -> list[dict[str, Any]]:
    """Filter chat events to only semantic terminal.* events."""
    return [
        e for e in harness.events["chat"]
        if e["data"].get("event_type", "").startswith("terminal.")
    ]


# ---------------------------------------------------------------------------
# Test: CrewAI expert stock-analysis flow
# Single async test with sequential steps (describe-style naming in logs).
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_crewai_expert_stocks_flow(nats_client, run_id, user_id):
    """CrewAI expert worker drives stock_analysis through the full state machine.

    Steps:
      1. worker_ready
      2. project_selection → send stock_analysis
      3. patch_approval → send approved
      4. CLI started (ProcessRunner)
      5. terminal state (completed/failed/cancelled)
      6. no legacy update_start
      7. semantic terminal.started
      8. semantic terminal.output (chunked)
      9. semantic terminal lifecycle end
      10. single terminal session
    """
    _ensure_image()
    container_name = f"crewai-expert-test-{run_id.replace(':', '-')}".lower()
    harness = WorkerTestHarness(nats_client, run_id, user_id)
    await harness.subscribe()
    logger.info("Subscribed to NATS events for run=%s user=%s", run_id, user_id)

    container_id = await asyncio.get_event_loop().run_in_executor(
        None, _start_container, run_id, user_id, container_name
    )

    log_task = await _stream_container_logs(container_name)

    try:
        # -- Step 1: worker_ready --
        logger.info("[step 1] waiting for worker_ready")
        ready = await harness.wait_for("ready", timeout=120.0)
        assert ready is not None, "worker_ready not received within 120s"
        assert ready["data"]["event_type"] == "worker_ready"
        logger.info("[step 1] PASSED — worker_ready received")

        # -- Step 2: project selection --
        logger.info("[step 2] waiting for project selection prompt")
        event = await _wait_for_state(
            harness, event_type="waiting_input", reason="project_selection", timeout=120.0
        )
        assert event is not None, "project selection waiting_input not received"
        options = _parse_approval_options(event)
        assert "options" in options, f"No options in payload: {options}"
        assert PROJECT_NAME in options["options"], f"{PROJECT_NAME} not in {options['options']}"
        logger.info("[step 2] project selection offered %d options", len(options["options"]))
        await _send_input(nats_client, run_id, user_id, PROJECT_NAME)
        logger.info("[step 2] PASSED — sent selection: %s", PROJECT_NAME)

        # -- Step 3: patch approval --
        logger.info("[step 3] waiting for patch approval prompt")
        patch_event = await _wait_for_state(
            harness, event_type="waiting_input", reason="patch_approval", timeout=120.0
        )
        assert patch_event is not None, "patch approval waiting_input not received"
        await _send_input(nats_client, run_id, user_id, "approved")
        logger.info("[step 3] PASSED — patch approved")

        # -- Step 4: CLI started --
        logger.info("[step 4] waiting for ProcessRunner started (dep sync may take minutes)")
        started_event = await _wait_for_state(harness, event_type="started", timeout=600.0)
        assert started_event is not None, "ProcessRunner 'started' not received"
        logger.info("[step 4] PASSED — CLI started: %s",
                    started_event.get("payload", {}).get("command", "?"))

        # -- Step 5: terminal state --
        logger.info("[step 5] waiting for terminal state")
        terminal = await _wait_for_terminal_state(harness, timeout=60.0)
        assert terminal is not None, "Graph did not reach terminal state"
        assert terminal in {"completed", "failed", "cancelled"}
        logger.info("[step 5] PASSED — terminal state: %s", terminal)

        # -- Step 6: no legacy update_start_crewai_cli --
        for ev in harness.events["state"]:
            status = ev["data"].get("payload", {}).get("status", "")
            assert status.lower() != "update_start_crewai_cli", (
                f"Legacy UPDATE_START_CREWAI_CLI found: {ev}"
            )
        logger.info("[step 6] PASSED — no legacy states")

        # -- Step 7: semantic terminal.started --
        terminal_chat_events = _get_terminal_chat_events(harness)
        types = {e["data"]["event_type"] for e in terminal_chat_events}
        logger.info("[step 7] semantic terminal types=%s count=%d", types, len(terminal_chat_events))
        assert "terminal.started" in types, f"Missing terminal.started in {types}"
        started_ev = next(e for e in terminal_chat_events if e["data"]["event_type"] == "terminal.started")
        p = started_ev["data"]["payload"]
        assert p["event_type"] == "terminal.started"
        assert "terminal_session_id" in p
        assert "command" in p
        assert "sequence" in p
        logger.info("[step 7] PASSED — terminal.started command=%s", p.get("command", "")[:60])

        # -- Step 8: semantic terminal.output chunking (if any output was emitted) --
        outputs = [e for e in terminal_chat_events if e["data"]["event_type"] == "terminal.output"]
        for oe in outputs:
            op = oe["data"]["payload"]
            assert "chunk_index" in op, "missing chunk_index"
            assert "chunk_count" in op, "missing chunk_count"
            assert "data" in op, "missing data"
            assert "terminal_session_id" in op, "missing terminal_session_id"
            assert "output_id" in op, "missing output_id"
        logger.info("[step 8] PASSED — %d output chunks validated", len(outputs))

        # -- Step 9: terminal lifecycle end --
        end_types = types & {"terminal.completed", "terminal.failed", "terminal.cancelled"}
        assert end_types, f"Missing terminal end event in {types}"
        logger.info("[step 9] PASSED — lifecycle end: %s", end_types)

        # -- Step 10: single terminal session --
        session_ids = {
            e["data"]["payload"]["terminal_session_id"]
            for e in terminal_chat_events
            if "terminal_session_id" in e["data"].get("payload", {})
        }
        assert len(session_ids) == 1, f"Expected 1 session, got {session_ids}"
        logger.info("[step 10] PASSED — single session: %s", session_ids.pop()[:16])

        logger.info("ALL STEPS PASSED")

    finally:
        log_task.cancel()
        try:
            await log_task
        except asyncio.CancelledError:
            pass
        await harness.cleanup()
        if container_id:
            await asyncio.get_event_loop().run_in_executor(
                None, _stop_container, container_name
            )

