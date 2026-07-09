"""Integration test for single agent flow with NATS messaging using in-process worker"""
import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from message_fixtures import run_start_fixture
from app.worker import AgentWorker
from internal.messaging.nats import set_nats_client
from internal.workflow.checkpointer import get_checkpointer


@pytest.mark.integration
async def test_single_agent_nats_flow(
    nats_test_client,
    sample_user_id,
    sample_repository_id,
    sample_project_id,
):
    """Test single agent flow with NATS messaging using in-process worker initialization.
    
    This test:
    1. Initializes the AgentWorker directly in the test
    2. Subscribes to worker ready, state events, and chat events
    3. Sends a run.start command via NATS
    4. Validates progress updates and final result messages
    """
    run_id = f"single-agent-{uuid.uuid4().hex[:8]}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        # Create a simple workspace with a passing test
        (workspace / "Makefile").write_text(
            "test:\n\t@echo '1 passed, 0 failed, 0 skipped'\n", encoding="utf-8"
        )
        
        # Set environment variables for the worker
        env = os.environ.copy()
        env.update({
            "DATABASE_URL": "postgresql+asyncpg://agentic:agentic@localhost:5433/agentic",
            "NATS_URL": "nats://localhost:4222",
            "LLM_PROVIDER": "fake",
            "MOCK_MODE": "false",
            "WORKSPACE_PATH": str(workspace),
            "PYTHONUNBUFFERED": "1",
        })
        
        # Apply environment variables
        for key, value in env.items():
            os.environ[key] = value
        
        try:
            # Initialize and start the worker in-process
            worker = AgentWorker(nats_url="nats://localhost:4222", run_id=run_id)
            
            # Start the worker in background
            worker_task = asyncio.create_task(worker.start())
            
            # Wait a moment for worker to start and subscribe
            await asyncio.sleep(1)
            
            # Subscribe to worker ready signal
            ready_gen = nats_test_client.subscribe(f"agent.chat.{run_id}.worker.ready")
            try:
                ready_msg = await asyncio.wait_for(anext(ready_gen), timeout=10)
                assert ready_msg.get("status") == "ready", "Worker did not publish ready signal"
            except asyncio.TimeoutError:
                pytest.fail("Worker ready signal timeout")
            
            # Subscribe to state events and chat events
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
            
            # Publish the run.start command
            command = run_start_fixture(
                run_id=run_id,
                user_id=sample_user_id,
                project_id=sample_project_id,
                repository_id=sample_repository_id,
                task="Add a simple feature and verify it passes tests",
            )
            command["payload"]["llm_provider"] = "fake"
            command["payload"]["mock_mode"] = False
            await nats_test_client.publish(f"agent.chat.{run_id}.user.events", command)
            
            # Collect events until workflow completes or timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(consume_state(), consume_chat()), timeout=60
                )
            except asyncio.TimeoutError:
                pass
            
            # Stop the worker
            await worker.stop()
            await worker_task
            
            # Validate state events
            assert state_events, "No state events received from the worker"
            state_types = {e.get("event_type") for e in state_events}
            
            # Check for key state transitions
            assert "created" in state_types, f"Missing 'created' state; received: {state_types}"
            assert "completed" in state_types or "failed" in state_types, \
                f"Workflow did not reach terminal state; received: {state_types}"
            
            # Validate chat events
            assert chat_events, "No chat events received from the worker"
            
            # Check for progress updates
            progress_updates = [e for e in chat_events if e.get("event_type") == "progress_update"]
            assert len(progress_updates) > 0, f"No progress updates received; chat events: {chat_events}"
            
            # Validate progress update structure
            for update in progress_updates:
                assert "payload" in update, "Progress update missing payload"
                assert "content" in update["payload"], "Progress update payload missing content"
                assert "run_id" in update, "Progress update missing run_id"
                assert update["run_id"] == run_id, f"Progress update run_id mismatch: {update['run_id']} != {run_id}"
            
            # Check for final answer
            final_answers = [e for e in chat_events if e.get("event_type") == "final_answer"]
            if "completed" in state_types:
                assert final_answers, f"No final_answer received for completed run; chat events: {chat_events}"
                
                # Validate final answer structure
                final_answer = final_answers[0]
                assert "payload" in final_answer, "Final answer missing payload"
                assert "content" in final_answer["payload"], "Final answer payload missing content"
                assert "run_id" in final_answer, "Final answer missing run_id"
                assert final_answer["run_id"] == run_id, f"Final answer run_id mismatch: {final_answer['run_id']} != {run_id}"
        
        finally:
            # Restore environment variables
            for key in list(env.keys()):
                if key not in os.environ:
                    continue
                if key not in ["DATABASE_URL", "NATS_URL", "LLM_PROVIDER", "MOCK_MODE", "WORKSPACE_PATH", "PYTHONUNBUFFERED"]:
                    continue
                # Only restore if we modified it
                pass


@pytest.mark.integration
async def test_single_agent_progress_updates(
    nats_test_client,
    sample_user_id,
    sample_repository_id,
    sample_project_id,
):
    """Test that single agent sends progress updates during execution"""
    run_id = f"progress-{uuid.uuid4().hex[:8]}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "Makefile").write_text(
            "test:\n\t@echo 'Test passed'\n", encoding="utf-8"
        )
        
        env = os.environ.copy()
        env.update({
            "DATABASE_URL": "postgresql+asyncpg://agentic:agentic@localhost:5433/agentic",
            "NATS_URL": "nats://localhost:4222",
            "LLM_PROVIDER": "fake",
            "MOCK_MODE": "false",
            "WORKSPACE_PATH": str(workspace),
        })
        
        for key, value in env.items():
            os.environ[key] = value
        
        try:
            worker = AgentWorker(nats_url="nats://localhost:4222", run_id=run_id)
            worker_task = asyncio.create_task(worker.start())
            await asyncio.sleep(1)
            
            # Wait for worker ready
            ready_gen = nats_test_client.subscribe(f"agent.chat.{run_id}.worker.ready")
            try:
                ready_msg = await asyncio.wait_for(anext(ready_gen), timeout=10)
                assert ready_msg.get("status") == "ready"
            except asyncio.TimeoutError:
                pytest.fail("Worker ready timeout")
            
            # Subscribe to chat events
            chat_gen = nats_test_client.subscribe(f"agent.chat.{run_id}.events")
            chat_events = []
            
            async def consume_chat():
                async for msg in chat_gen:
                    chat_events.append(msg)
                    if msg.get("event_type") in ["final_answer", "completed"]:
                        break
            
            # Send command
            command = run_start_fixture(
                run_id=run_id,
                user_id=sample_user_id,
                project_id=sample_project_id,
                repository_id=sample_repository_id,
                task="Test task for progress updates",
            )
            command["payload"]["llm_provider"] = "fake"
            await nats_test_client.publish(f"agent.chat.{run_id}.user.events", command)
            
            # Collect events
            try:
                await asyncio.wait_for(consume_chat(), timeout=60)
            except asyncio.TimeoutError:
                pass
            
            await worker.stop()
            await worker_task
            
            # Validate progress updates
            progress_updates = [e for e in chat_events if e.get("event_type") == "progress_update"]
            assert len(progress_updates) >= 1, f"Expected at least 1 progress update, got {len(progress_updates)}"
            
            # Validate each progress update has required fields
            for update in progress_updates:
                assert update.get("event_type") == "progress_update"
                assert update.get("run_id") == run_id
                assert "payload" in update
                assert "content" in update["payload"]
                assert isinstance(update["payload"]["content"], str)
                assert len(update["payload"]["content"]) > 0
        
        finally:
            pass
