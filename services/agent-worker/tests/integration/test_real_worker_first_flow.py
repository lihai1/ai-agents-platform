"""Integration test for the agent-worker first flow with a real worker process."""
import asyncio
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

from message_fixtures import run_start_fixture


@pytest.mark.integration
async def test_worker_first_flow_real_skill_lead(
    nats_test_client,
    sample_user_id,
    sample_repository_id,
    sample_project_id,
):
    """Run the real agent-worker with real NATS/Postgres and verify the first flow.

    The worker executes the real SkillsLeadAgent/RepoScoutAgent/SolutionPlannerAgent
    code (using the fake LLM so no external model is required). A passing Makefile is
    provided in the temporary workspace so the completion verifier accepts the run.
    """
    run_id = f"first-flow-{uuid.uuid4().hex[:8]}"
    worker_cwd = Path(__file__).resolve().parents[2]

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        # Simulate a passing test suite so the verifier can accept the run.
        (workspace / "Makefile").write_text(
            "test:\n\t@echo '1 passed, 0 failed, 0 skipped'\n", encoding="utf-8"
        )

        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": "postgresql+asyncpg://agentic:agentic@localhost:5433/agentic",
                "NATS_URL": "nats://localhost:4222",
                "LLM_PROVIDER": "fake",
                "MOCK_MODE": "false",
                "WORKSPACE_PATH": str(workspace),
                "PYTHONUNBUFFERED": "1",
            }
        )

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.worker",
            "--run-id",
            run_id,
            "--nats-url",
            "nats://localhost:4222",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(worker_cwd),
        )

        try:
            # Wait for the worker to subscribe and publish its ready signal.
            ready_gen = nats_test_client.subscribe(f"agent.control.container.ready")
            ready_msg = await asyncio.wait_for(anext(ready_gen), timeout=10)
            assert ready_msg.get("status") == "ready", "Worker did not publish ready signal"

            # Subscribe to the worker's state and chat events.
            state_gen = nats_test_client.subscribe(f"agent.events.{run_id}.>")
            chat_gen = nats_test_client.subscribe(f"agent.chat.{run_id}.events")

            state_events = []
            chat_events = []
            terminal = {"completed", "failed", "cancelled", "budget_exceeded"}

            async def consume_state():
                async for msg in state_gen:
                    state_events.append(msg)
                    if msg.get("event_type") in terminal:
                        break

            async def consume_chat():
                async for msg in chat_gen:
                    chat_events.append(msg)
                    if msg.get("event_type") == "final_answer":
                        break

            # Publish the run.start command that triggers the workflow.
            command = run_start_fixture(
                run_id=run_id,
                user_id=sample_user_id,
                project_id=sample_project_id,
                repository_id=sample_repository_id,
                task="Add a simple Go feature and verify it passes tests",
            )
            command["payload"]["llm_provider"] = "fake"
            command["payload"]["mock_mode"] = False
            await nats_test_client.publish(f"agent.chat.{run_id}.start", command)

            # Collect events until the workflow reaches a terminal state or timeout.
            try:
                await asyncio.wait_for(
                    asyncio.gather(consume_state(), consume_chat()), timeout=60
                )
            except asyncio.TimeoutError:
                pass

            stdout, _ = await proc.communicate()
            log = stdout.decode("utf-8", errors="replace")
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

        # Verify the first flow produced the expected state sequence.
        assert state_events, "No state events received from the worker"
        state_types = {e.get("event_type") for e in state_events}
        expected = {
            "created",
            "preparing_workspace",
            "scouting",
            "planning",
            "designing",
            "implementing",
            "testing",
            "reviewing",
            "verifying",
            "completed",
        }
        assert state_types.issuperset(
            {"created", "preparing_workspace", "scouting", "planning", "completed"}
        ), f"Missing expected state events; received: {state_types}"
        assert "completed" in state_types, f"Workflow did not complete; received: {state_types}"

        # Verify the final answer was delivered to the chat subject.
        final_answers = [e for e in chat_events if e.get("event_type") == "final_answer"]
        assert final_answers, f"No final_answer received; chat events: {chat_events}"

        # Verify the worker logs show the expected first-flow behavior.
        assert "completed with status completed" in log, (
            f"Worker log does not show completion:\n{log[:2000]}"
        )
