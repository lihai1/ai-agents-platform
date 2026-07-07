"""E2E test configuration"""
import pytest
import asyncio
import os
from httpx import AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_client():
    """Create test HTTP client"""
    base_url = os.getenv("TEST_BASE_URL", "http://localhost:8000")
    async with AsyncClient(base_url=base_url) as client:
        yield client


@pytest.fixture(autouse=True)
async def cleanup_runs(test_client):
    """Clean up test runs after each test"""
    yield
    
    # Clean up any test runs created during the test
    # In production, this would query for test runs and delete them
    pass
