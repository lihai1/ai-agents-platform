"""Integration test for agent-worker NATS flow"""
import pytest
import asyncio
import sys
import os
import json
from nats.aio.client import Client as NATSClient

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from internal.messaging.nats import NATSMessaging


# Shared test IDs
RUN_ID = "integration-test-run-001"
USER_ID = "test-user-001"


@pytest.fixture
async def nats_connection():
    """Provide NATS connection for tests"""
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = NATSClient()
    await nc.connect(nats_url)
    yield nc
    await nc.close()


@pytest.mark.integration
async def test_agent_worker_nats_flow(nats_connection):
    """Test that NATSMessaging.publish_control_ready publishes agent.control.worker.{run_id}.ready"""
    
    # prepareAndSendTestRelatedInputs
    nats_messaging, sub, message_received, received_message_container = await prepareAndSendTestRelatedInputs(nats_connection)
    
    try:
        # FunctionUnderTest
        await publishWorkerReadyMessage(nats_messaging)
        
        # ExpectRelatedNatsOutput
        received_message = await expectWorkerReadyNatsOutput(message_received, received_message_container)
        
        # Verify message content
        assert received_message.get("run_id") == RUN_ID
        assert received_message.get("event_type") == "worker_ready"
        assert "payload" in received_message
        
        payload = received_message["payload"]
        assert payload.get("status") == "ready"
        
    finally:
        # Cleanup
        await nats_messaging.close()
        if sub:
            await sub.unsubscribe()


async def prepareAndSendTestRelatedInputs(nats_connection):
    """Prepare NATS client and subscription for agent-worker test"""
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nats_messaging = NATSMessaging(nats_url=nats_url)
    await nats_messaging.connect()
    
    # Subscribe to agent.control.worker.{run_id}.ready to capture the ready signal
    message_received = asyncio.Event()
    received_message_container = {"message": None}
    sub = None
    
    async def message_handler(msg):
        data = msg.data.decode()
        message = json.loads(data)
        if message.get("run_id") == RUN_ID:
            received_message_container["message"] = message
            message_received.set()
    
    # Use JetStream to subscribe (since publish_control_ready uses JetStream)
    js = nats_connection.jetstream()
    sub = await js.subscribe(
        subject="agent.control.worker.>",
        stream="AGENT_CONTROL",
        cb=message_handler,
        manual_ack=True,
    )
    
    return nats_messaging, sub, message_received, received_message_container


async def publishWorkerReadyMessage(nats_messaging):
    """FunctionUnderTest: publish_control_ready"""
    await nats_messaging.publish_control_ready(
        run_id=RUN_ID,
        user_id=USER_ID,
    )


async def expectWorkerReadyNatsOutput(message_received, received_message_container):
    """ExpectRelatedNatsOutput: ready message should be received"""
    try:
        await asyncio.wait_for(message_received.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("Timeout waiting for agent.control.worker.{run_id}.ready message")
    return received_message_container["message"]


# Standalone entry point
if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", "-s"])
