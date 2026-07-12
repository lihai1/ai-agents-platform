"""Integration test configuration for agent-worker"""
import pytest
import asyncio
import sys
import os

# Add shared test tools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../shared/test-tools"))

from nats_helpers import nats_client


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def nats_test_client():
    """Provide NATS test client for tests"""
    async with nats_client() as client:
        yield client
