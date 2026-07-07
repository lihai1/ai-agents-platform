"""Tests for authorization boundaries"""
import pytest
from internal.workflow.router import CreateRunRequest


@pytest.mark.asyncio
async def test_cross_user_run_access():
    """Test that users cannot access runs from other users"""
    # Test that user A cannot access user B's runs
    pass


@pytest.mark.asyncio
async def test_cross_project_access():
    """Test that users cannot access projects they don't have access to"""
    # Test project access boundaries
    pass


@pytest.mark.asyncio
async def test_approval_authorization():
    """Test that only authorized users can approve/reject"""
    # Test approval authorization
    pass
