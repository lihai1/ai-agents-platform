"""Integration tests for agent-worker flow using pytest-describe syntax.

These tests demonstrate:
1. Starting an agent-worker instance and expecting NATS messages
2. Starting an agent-worker instance, sending user events, and expecting responses

Based on NATS flow:
- agent-worker publishes to: agent.user.{user_id}.events.{run_id}.state.{event_type}
- agent-worker publishes to: agent.user.{user_id}.chat.{run_id}.worker.events
- agent-worker subscribes to: agent.user.{user_id}.chat.{run_id}.user.events
"""
import pytest
import uuid
import asyncio
import os
from unittest.mock import AsyncMock, patch
from app.worker import AgentWorker
from test_helpers import WorkerTestHelper, setup_worker_env, create_user_event


def describe_worker_flow():
    """Agent-worker integration test flows."""
    
    @pytest.mark.integration
    async def test_starts_worker_and_expects_state_events(nats_test_client):
        """Test flow: Start agent-worker instance, expect agent NATS state messages.
        
        Flow:
        1. Subscribe to worker state events
        2. Create and start AgentWorker instance
        3. Mock handle_run_start to publish state events
        4. Verify worker publishes state events
        5. Stop worker and cleanup
        
        Expected NATS messages:
        - agent.user.{user_id}.events.{run_id}.state.created
        - agent.user.{user_id}.events.{run_id}.state.running
        """
        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-123"
        
        # Setup test helper
        helper = WorkerTestHelper(nats_test_client)
        await helper.subscribe_to_worker_events(user_id, run_id, timeout=5.0)
        
        # Setup worker environment
        setup_worker_env(run_id, user_id)
        
        # Mock handle_run_start to publish state events
        async def mock_handle_run_start(run_id, payload, create_run, get_checkpointer, worker):
            # Simulate worker publishing state events
            await worker.nats.publish_event("created", run_id, {"status": "created"}, user_id)
            await asyncio.sleep(0.1)
            await worker.nats.publish_event("running", run_id, {"status": "running"}, user_id)
        
        try:
            # Create and start worker
            with patch("app.worker.handle_run_start", side_effect=mock_handle_run_start):
                worker = AgentWorker(nats_url="nats://localhost:4222", run_id=run_id)
                await worker.start()
                
                # Wait for state events with 5-second timeout
                created_event = await helper.wait_for_event(run_id, "created", timeout=5.0)
                running_event = await helper.wait_for_event(run_id, "running", timeout=5.0)
                
                # Verify events were received
                assert created_event is not None, "Expected 'created' event within 5 seconds"
                assert running_event is not None, "Expected 'running' event within 5 seconds"
                assert created_event["data"]["event_type"] == "created"
                assert running_event["data"]["event_type"] == "running"
                
                # Verify worker is running
                assert worker.running
                
        finally:
            await helper.cleanup()
            if 'worker' in locals():
                await worker.stop()
    
    @pytest.mark.integration
    async def test_starts_worker_and_handles_user_events(nats_test_client):
        """Test flow: Start agent-worker, send user events, expect agent NATS messages.
        
        Flow:
        1. Subscribe to worker chat events
        2. Create and start AgentWorker instance
        3. Mock handle_run_start to handle user events
        4. Send user event (approval)
        5. Verify worker processes and responds with chat event
        6. Stop worker and cleanup
        
        Expected NATS messages:
        - agent.user.{user_id}.chat.{run_id}.user.events (sent by test)
        - agent.user.{user_id}.chat.{run_id}.worker.events (response from worker)
        """
        run_id = f"test-run-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-123"
        
        # Setup test helper
        helper = WorkerTestHelper(nats_test_client)
        await helper.subscribe_to_worker_chat_events(user_id, run_id, timeout=5.0)
        
        # Setup worker environment
        setup_worker_env(run_id, user_id)
        
        # Track if user event was received
        user_event_received = asyncio.Event()
        
        # Mock handle_run_start to handle user events
        async def mock_handle_run_start(run_id, payload, create_run, get_checkpointer, worker):
            # Wait for user event
            await user_event_received.wait()
            
            # Respond with chat event
            await worker.nats.publish_chat_event(
                "approval_processed",
                run_id,
                {"status": "approved", "message": "Tool approved"},
                user_id
            )
        
        try:
            # Create and start worker
            with patch("app.worker.handle_run_start", side_effect=mock_handle_run_start):
                worker = AgentWorker(nats_url="nats://localhost:4222", run_id=run_id)
                await worker.start()
                
                # Send user event (approval)
                user_event = create_user_event(run_id, user_id, "approval", approved=True)
                subject = f"agent.user.{user_id}.chat.{run_id}.user.events"
                await nats_test_client.publish(subject, user_event)
                
                # Signal that user event was sent
                user_event_received.set()
                
                # Wait for chat event response with 5-second timeout
                chat_event = await helper.wait_for_chat_event(run_id, "approval_processed", timeout=5.0)
                
                # Verify chat event was received
                assert chat_event is not None, "Expected 'approval_processed' chat event within 5 seconds"
                assert chat_event["data"]["event_type"] == "approval_processed"
                assert chat_event["data"]["payload"]["status"] == "approved"
                
                # Verify worker is still running
                assert worker.running
                
        finally:
            await helper.cleanup()
            if 'worker' in locals():
                await worker.stop()
