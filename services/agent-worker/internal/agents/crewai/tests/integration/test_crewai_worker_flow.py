"""Integration tests for CrewAI worker flow using pytest-describe syntax.

These tests demonstrate:
1. Starting a CrewAI worker instance and expecting NATS messages
2. Starting a CrewAI worker instance, sending user events, and expecting responses
3. Testing prompt detection and input handling
4. Testing final_answer with real process output

Based on NATS flow:
- CrewAI worker publishes to: agent.user.{user_id}.events.{run_id}.state.{event_type}
- CrewAI worker publishes to: agent.user.{user_id}.chat.{run_id}.worker.events
- CrewAI worker subscribes to: agent.user.{user_id}.chat.{run_id}.user.events
"""
import pytest
import uuid
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from agent_worker.nats_client import CrewAINatsClient
from agent_worker.runner import ProcessRunner
from agent_worker.config import Config
from agent_worker.subjects import SubjectTemplates


class CrewAITestHelper:
    """Helper class for CrewAI worker integration tests"""

    def __init__(self, nats_client):
        self.nc = nats_client
        self.collected_events = {}
        self.subscriptions = []

    async def subscribe_to_worker_events(
        self,
        user_id: str,
        run_id: str,
        timeout: float = 5.0,
    ) -> None:
        """Subscribe to worker state events with timeout"""
        subject = f"agent.user.{user_id}.events.{run_id}.state.>"
        self.collected_events[f"state_{run_id}"] = []

        async def event_handler(msg):
            try:
                import json
                data = json.loads(msg.data.decode())
                self.collected_events[f"state_{run_id}"].append({
                    "subject": msg.subject,
                    "data": data,
                })
            except Exception as e:
                print(f"Error processing event: {e}")

        sub = await self.nc.nc.subscribe(subject, cb=event_handler)
        self.subscriptions.append(sub)

    async def subscribe_to_worker_chat_events(
        self,
        user_id: str,
        run_id: str,
        timeout: float = 5.0,
    ) -> None:
        """Subscribe to worker chat events with timeout"""
        subject = f"agent.user.{user_id}.chat.{run_id}.events"
        self.collected_events[f"chat_{run_id}"] = []

        async def chat_handler(msg):
            try:
                import json
                data = json.loads(msg.data.decode())
                self.collected_events[f"chat_{run_id}"].append({
                    "subject": msg.subject,
                    "data": data,
                })
            except Exception as e:
                print(f"Error processing chat event: {e}")

        sub = await self.nc.nc.subscribe(subject, cb=chat_handler)
        self.subscriptions.append(sub)

    async def wait_for_event(
        self,
        run_id: str,
        event_type: str,
        timeout: float = 5.0,
    ):
        """Wait for a specific event type with timeout"""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if f"state_{run_id}" in self.collected_events:
                for event in self.collected_events[f"state_{run_id}"]:
                    if event["data"].get("event_type") == event_type:
                        return event
            await asyncio.sleep(0.1)

        return None

    async def wait_for_chat_event(
        self,
        run_id: str,
        event_type: str,
        timeout: float = 5.0,
    ):
        """Wait for a specific chat event type with timeout"""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if f"chat_{run_id}" in self.collected_events:
                for event in self.collected_events[f"chat_{run_id}"]:
                    if event["data"].get("event_type") == event_type:
                        return event
            await asyncio.sleep(0.1)

        return None

    def get_state_events(self, run_id: str):
        """Get all collected state events for a run"""
        return self.collected_events.get(f"state_{run_id}", [])

    def get_chat_events(self, run_id: str):
        """Get all collected chat events for a run"""
        return self.collected_events.get(f"chat_{run_id}", [])

    async def cleanup(self) -> None:
        """Clean up subscriptions"""
        for sub in self.subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                print(f"Error unsubscribing: {e}")
        self.subscriptions.clear()


def setup_crewai_env(run_id: str, user_id: str = "test-user-123") -> None:
    """Set up environment variables for CrewAI worker tests"""
    os.environ["USER_ID"] = user_id
    os.environ["RUN_ID"] = run_id
    os.environ["NATS_URL"] = "nats://localhost:4222"
    os.environ["WORKSPACE_PATH"] = "/tmp/test_workspace"


def create_user_event(
    run_id: str,
    user_id: str,
    event_type: str = "user_input",
    input_text: str = "test input",
) -> dict:
    """Create a user event message for testing"""
    return {
        "message_id": str(uuid.uuid4()),
        "event_type": event_type,
        "run_id": run_id,
        "payload": {
            "type": event_type,
            "input": input_text,
        },
        "timestamp": "2026-07-10T10:19:53.178810",
        "schema_version": "1.0",
    }


@pytest.fixture
async def nats_test_client():
    """Fixture for NATS test client"""
    from nats.aio.client import Client as NATSClient
    nc = NATSClient()
    await nc.connect("nats://localhost:4222")
    yield nc
    await nc.close()


def describe_crewai_worker_flow():
    """CrewAI worker integration test flows."""

    @pytest.mark.integration
    async def test_nats_client_connects_and_publishes_state(nats_test_client):
        """Test CrewAI NATS client connects and publishes state events."""
        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-123"

        setup_crewai_env(run_id, user_id)

        helper = CrewAITestHelper(nats_test_client)
        await helper.subscribe_to_worker_events(user_id, run_id, timeout=5.0)

        try:
            client = CrewAINatsClient(
                nats_url="nats://localhost:4222",
                uid=user_id,
                run_id=run_id,
            )
            await client.connect()

            # Publish a state event
            await client.publish_state("started", {"status": "started"})

            # Wait for the event
            event = await helper.wait_for_event(run_id, "started", timeout=5.0)

            assert event is not None, "Expected 'started' event within 5 seconds"
            assert event["data"]["event_type"] == "started"
            assert event["data"]["payload"]["status"] == "started"

        finally:
            await helper.cleanup()
            if 'client' in locals():
                await client.close()

    @pytest.mark.integration
    async def test_nats_client_publishes_chat_events(nats_test_client):
        """Test CrewAI NATS client publishes chat events."""
        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-123"

        setup_crewai_env(run_id, user_id)

        helper = CrewAITestHelper(nats_test_client)
        await helper.subscribe_to_worker_chat_events(user_id, run_id, timeout=5.0)

        try:
            client = CrewAINatsClient(
                nats_url="nats://localhost:4222",
                uid=user_id,
                run_id=run_id,
            )
            await client.connect()

            # Publish a chat event
            await client.publish_chat("progress_update", {"message": "Working..."})

            # Wait for the event
            event = await helper.wait_for_chat_event(run_id, "progress_update", timeout=5.0)

            assert event is not None, "Expected 'progress_update' chat event within 5 seconds"
            assert event["data"]["event_type"] == "progress_update"
            assert event["data"]["payload"]["message"] == "Working..."

        finally:
            await helper.cleanup()
            if 'client' in locals():
                await client.close()

    @pytest.mark.integration
    async def test_runner_simple_command_success(nats_test_client):
        """Test ProcessRunner with a simple successful command."""
        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-123"

        setup_crewai_env(run_id, user_id)

        helper = CrewAITestHelper(nats_test_client)
        await helper.subscribe_to_worker_events(user_id, run_id, timeout=5.0)
        await helper.subscribe_to_worker_chat_events(user_id, run_id, timeout=5.0)

        try:
            client = CrewAINatsClient(
                nats_url="nats://localhost:4222",
                uid=user_id,
                run_id=run_id,
            )
            await client.connect()

            # Create a temporary workspace
            with tempfile.TemporaryDirectory() as tmpdir:
                workspace = Path(tmpdir)

                # Run a simple echo command
                runner = ProcessRunner(
                    nats=client,
                    command='echo "Hello from CrewAI"',
                    cwd=workspace,
                    input_idle_seconds=2.0,
                    output_max_buffer_chars=1000,
                )

                await runner.run()

                # Wait for started event
                started = await helper.wait_for_event(run_id, "started", timeout=5.0)
                assert started is not None, "Expected 'started' event"

                # Wait for completed event
                completed = await helper.wait_for_event(run_id, "completed", timeout=5.0)
                assert completed is not None, "Expected 'completed' event"

                # Wait for final_answer chat event
                final = await helper.wait_for_chat_event(run_id, "final_answer", timeout=5.0)
                assert final is not None, "Expected 'final_answer' chat event"
                assert "Hello from CrewAI" in final["data"]["payload"]["content"]

        finally:
            await helper.cleanup()
            if 'client' in locals():
                await client.close()

    @pytest.mark.integration
    async def test_runner_accumulates_output_for_final_answer(nats_test_client):
        """Test that ProcessRunner accumulates all output for final_answer."""
        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-123"

        setup_crewai_env(run_id, user_id)

        helper = CrewAITestHelper(nats_test_client)
        await helper.subscribe_to_worker_chat_events(user_id, run_id, timeout=5.0)

        try:
            client = CrewAINatsClient(
                nats_url="nats://localhost:4222",
                uid=user_id,
                run_id=run_id,
            )
            await client.connect()

            with tempfile.TemporaryDirectory() as tmpdir:
                workspace = Path(tmpdir)

                # Run a command that produces multiple lines
                runner = ProcessRunner(
                    nats=client,
                    command='echo "Line 1" && echo "Line 2" && echo "Line 3"',
                    cwd=workspace,
                    input_idle_seconds=2.0,
                    output_max_buffer_chars=1000,
                )

                await runner.run()

                # Wait for final_answer
                final = await helper.wait_for_chat_event(run_id, "final_answer", timeout=5.0)
                assert final is not None, "Expected 'final_answer' chat event"

                content = final["data"]["payload"]["content"]
                assert "Line 1" in content
                assert "Line 2" in content
                assert "Line 3" in content

        finally:
            await helper.cleanup()
            if 'client' in locals():
                await client.close()

    @pytest.mark.integration
    async def test_runner_command_failure(nats_test_client):
        """Test ProcessRunner with a failing command."""
        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-123"

        setup_crewai_env(run_id, user_id)

        helper = CrewAITestHelper(nats_test_client)
        await helper.subscribe_to_worker_events(user_id, run_id, timeout=5.0)

        try:
            client = CrewAINatsClient(
                nats_url="nats://localhost:4222",
                uid=user_id,
                run_id=run_id,
            )
            await client.connect()

            with tempfile.TemporaryDirectory() as tmpdir:
                workspace = Path(tmpdir)

                # Run a command that fails
                runner = ProcessRunner(
                    nats=client,
                    command='exit 1',
                    cwd=workspace,
                    input_idle_seconds=2.0,
                    output_max_buffer_chars=1000,
                )

                await runner.run()

                # Wait for failed event
                failed = await helper.wait_for_event(run_id, "failed", timeout=5.0)
                assert failed is not None, "Expected 'failed' event"
                assert failed["data"]["payload"]["status"] == "failed"

        finally:
            await helper.cleanup()
            if 'client' in locals():
                await client.close()
