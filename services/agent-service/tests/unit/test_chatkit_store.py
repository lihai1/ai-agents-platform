"""Unit tests for PostgreSQLStore — ChatKit Store interface contract.

These tests use an in-memory SQLite-like approach via SQLAlchemy async
with a real PostgreSQL database (integration). For pure unit tests,
we mock the session factory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internal.chatkit.context import RequestContext
from internal.chatkit.store import PostgreSQLStore


def _make_context(user_subject: str = "user:test-user") -> RequestContext:
    """Create a minimal RequestContext for testing."""
    return RequestContext(
        user_subject=user_subject,
        org_id="org:test",
        request_id="req-123",
        authorization="Bearer test-token",
    )


class TestGenerateIds:
    """Test ID generation methods."""

    def test_generate_thread_id_format(self):
        store = PostgreSQLStore(MagicMock())
        context = _make_context()
        thread_id = store.generate_thread_id(context)
        assert thread_id.startswith("run-")
        # Should be valid UUID after prefix
        uuid_part = thread_id[4:]
        uuid.UUID(uuid_part)  # Raises if invalid

    def test_generate_item_id_format(self):
        store = PostgreSQLStore(MagicMock())
        context = _make_context()
        thread = MagicMock()
        item_id = store.generate_item_id("message", thread, context)
        assert item_id.startswith("item-")
        uuid_part = item_id[5:]
        uuid.UUID(uuid_part)  # Raises if invalid

    def test_generate_thread_id_unique(self):
        store = PostgreSQLStore(MagicMock())
        context = _make_context()
        ids = {store.generate_thread_id(context) for _ in range(100)}
        assert len(ids) == 100

    def test_generate_item_id_unique(self):
        store = PostgreSQLStore(MagicMock())
        context = _make_context()
        thread = MagicMock()
        ids = {store.generate_item_id("message", thread, context) for _ in range(100)}
        assert len(ids) == 100


class TestOwnershipVerification:
    """Test that ownership checks prevent unauthorized access."""

    def test_verify_ownership_passes_for_matching_user(self):
        row = MagicMock()
        row.user_subject = "user:alice"
        row.id = "thread-1"
        context = _make_context(user_subject="user:alice")
        # Should not raise
        PostgreSQLStore._verify_ownership(row, context)

    def test_verify_ownership_fails_for_different_user(self):
        row = MagicMock()
        row.user_subject = "user:alice"
        row.id = "thread-1"
        context = _make_context(user_subject="user:bob")
        with pytest.raises(ValueError, match="not found"):
            PostgreSQLStore._verify_ownership(row, context)


class TestAttachmentsUnsupported:
    """Test that attachment operations raise NotImplementedError."""

    @pytest.fixture
    def store(self):
        return PostgreSQLStore(MagicMock())

    @pytest.fixture
    def context(self):
        return _make_context()

    @pytest.mark.asyncio
    async def test_save_attachment_raises(self, store, context):
        with pytest.raises(NotImplementedError, match="attachments"):
            await store.save_attachment(MagicMock(), context)

    @pytest.mark.asyncio
    async def test_load_attachment_raises(self, store, context):
        with pytest.raises(NotImplementedError, match="attachments"):
            await store.load_attachment("attach-1", context)

    @pytest.mark.asyncio
    async def test_delete_attachment_raises(self, store, context):
        with pytest.raises(NotImplementedError, match="attachments"):
            await store.delete_attachment("attach-1", context)


class TestStoreInterface:
    """Verify PostgreSQLStore implements the Store protocol."""

    def test_implements_store_interface(self):
        from chatkit.store import Store
        assert issubclass(PostgreSQLStore, Store)

    def test_has_all_abstract_methods(self):
        from chatkit.store import Store
        import inspect

        store_methods = {
            name
            for name, method in inspect.getmembers(Store, predicate=inspect.isfunction)
            if getattr(method, "__isabstractmethod__", False)
        }
        pg_methods = set(dir(PostgreSQLStore))
        missing = store_methods - pg_methods
        assert not missing, f"PostgreSQLStore is missing abstract methods: {missing}"
