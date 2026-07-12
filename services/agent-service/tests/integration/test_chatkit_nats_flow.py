"""Integration test for agent-service NATS flow"""
import pytest
import asyncio
import sys
import os
import json
from nats.aio.client import Client as NATSClient

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from internal.chatkit.nats_bridge import NatsBridge
from internal.messaging.nats import NATSMessaging


# Shared test IDs
RUN_ID = "integration-test-run-001"
USER_ID = "test-user-001"
PROJECT_ID = "test-project-001"
REPOSITORY_ID = "test-repo-001"
TASK = "Write a greeting function and verify it works"


@pytest.fixture
async def nats_connection():
    """Provide NATS connection for tests"""
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = NATSClient()
    await nc.connect(nats_url)
    yield nc
    await nc.close()


@pytest.mark.integration
async def test_agent_service_nats_flow(nats_connection):
    """Test that NatsBridge.publish_agent_start publishes agent.control.{run_id}.start"""
    
    # prepareAndSendTestRelatedInputs
    nats_messaging, nats_bridge, sub, message_received, received_message_container = await prepareAndSendTestRelatedInputs(nats_connection)
    
    try:
        # FunctionUnderTest
        await publishAgentStartMessage(nats_bridge)
        
        # ExpectRelatedNatsOutput
        received_message = await expectAgentStartNatsOutput(message_received, received_message_container)
        
        # Verify message content
        assert received_message.get("run_id") == RUN_ID
        assert "user_id" in received_message
        assert "task" in received_message
        assert received_message.get("task") == TASK
        
    finally:
        # Cleanup
        await nats_messaging.close()
        if sub:
            await sub.unsubscribe()


async def prepareAndSendTestRelatedInputs(nats_connection):
    """Prepare NATS client, bridge, and subscription for agent-service test"""
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nats_messaging = NATSMessaging(nats_url=nats_url)
    await nats_messaging.connect()
    
    nats_bridge = NatsBridge(nats_messaging)
    
    # Subscribe to agent.control.> to capture the start message
    message_received = asyncio.Event()
    received_message_container = {"message": None}
    sub = None
    
    async def message_handler(msg):
        data = msg.data.decode()
        message = json.loads(data)
        # Accept any agent.control.*.start message
        if ".start" in msg.subject:
            received_message_container["message"] = message
            message_received.set()
    
    # Use the test NATS connection to subscribe
    sub = await nats_connection.subscribe("agent.control.>", cb=message_handler)
    
    return nats_messaging, nats_bridge, sub, message_received, received_message_container


async def publishAgentStartMessage(nats_bridge):
    """FunctionUnderTest: publish_agent_start"""
    await nats_bridge.publish_agent_start(
        run_id=RUN_ID,
        conversation_id="thread-001",
        user_subject=USER_ID,
        prompt=TASK,
        metadata={
            "repository_id": REPOSITORY_ID,
            "project_id": PROJECT_ID,
            "mock_mode": False,
            "agent_type": "single-agent",
            "llm_provider": "fake",
        },
    )


async def expectAgentStartNatsOutput(message_received, received_message_container):
    """ExpectRelatedNatsOutput: start message should be received"""
    try:
        await asyncio.wait_for(message_received.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("Timeout waiting for agent.control.{run_id}.start message")
    return received_message_container["message"]


# Standalone entry point
if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", "-s"])
