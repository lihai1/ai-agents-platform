"""PostgreSQL-backed ChatKit Store implementing the official chatkit.store.Store interface."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from chatkit.store import Store
from chatkit.types import (
    Attachment,
    Page,
    ThreadItem,
    ThreadMetadata,
)
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from internal.chatkit.context import RequestContext
from internal.models import AgentRun, ChatKitItemRow, ChatKitThreadRow

logger = logging.getLogger(__name__)

# Type alias used by SDK for id generation routing
StoreItemType = str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_status(status_value) -> dict | None:
    """Convert status to the ThreadStatus dict format expected by the SDK."""
    if status_value is None:
        return None
    if isinstance(status_value, dict):
        return status_value
    if isinstance(status_value, str):
        return {"type": status_value}
    return {"type": "active"}


def _thread_from_row(row: ChatKitThreadRow) -> ThreadMetadata:
    """Reconstruct ThreadMetadata from a DB row."""
    data = dict(row.metadata_json) if row.metadata_json else {}
    data.setdefault("id", row.id)
    data.setdefault("title", row.title)
    data.setdefault("created_at", row.created_at.isoformat() if row.created_at else _now().isoformat())
    # Normalize status to SDK-expected format: {"type": "active"} not "active"
    raw_status = data.get("status") or row.status
    data["status"] = _normalize_status(raw_status)
    return ThreadMetadata.model_validate(data)


def _item_from_row(row: ChatKitItemRow) -> ThreadItem:
    """Reconstruct a typed ThreadItem from its persisted JSON."""
    from chatkit.types import ThreadItem as TI
    from pydantic import TypeAdapter

    adapter = TypeAdapter(TI)
    return adapter.validate_python(row.item_json)


class PostgreSQLStore(Store[RequestContext]):
    """Official ChatKit Store backed by PostgreSQL via SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    def generate_thread_id(self, context: RequestContext) -> str:
        return f"run-{uuid.uuid4()}"

    def generate_item_id(
        self,
        item_type: StoreItemType,
        thread: ThreadMetadata,
        context: RequestContext,
    ) -> str:
        return f"item-{uuid.uuid4()}"

    # ------------------------------------------------------------------
    # Thread operations
    # ------------------------------------------------------------------

    async def load_thread(self, thread_id: str, context: RequestContext) -> ThreadMetadata:
        async with self._session_factory() as session:
            row = await self._get_authorized_thread(session, thread_id, context)
            return _thread_from_row(row)

    async def save_thread(self, thread: ThreadMetadata, context: RequestContext) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.get(ChatKitThreadRow, thread.id)
                metadata_json = thread.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
                status_str = thread.status.type if thread.status else "active"
                if row is None:
                    row = ChatKitThreadRow(
                        id=thread.id,
                        user_subject=context.user_subject,
                        title=thread.title,
                        status=status_str,
                        metadata_json=metadata_json,
                        created_at=thread.created_at or _now(),
                    )
                    session.add(row)
                else:
                    self._verify_ownership(row, context)
                    row.title = thread.title
                    row.status = status_str
                    row.metadata_json = metadata_json
                    row.updated_at = _now()

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadMetadata]:
        async with self._session_factory() as session:
            query = select(ChatKitThreadRow).where(
                ChatKitThreadRow.user_subject == context.user_subject
            )

            if after:
                cursor_row = await session.get(ChatKitThreadRow, after)
                if cursor_row:
                    if order == "desc":
                        query = query.where(
                            (ChatKitThreadRow.created_at < cursor_row.created_at)
                            | (
                                (ChatKitThreadRow.created_at == cursor_row.created_at)
                                & (ChatKitThreadRow.id < cursor_row.id)
                            )
                        )
                    else:
                        query = query.where(
                            (ChatKitThreadRow.created_at > cursor_row.created_at)
                            | (
                                (ChatKitThreadRow.created_at == cursor_row.created_at)
                                & (ChatKitThreadRow.id > cursor_row.id)
                            )
                        )

            if order == "desc":
                query = query.order_by(
                    ChatKitThreadRow.created_at.desc(), ChatKitThreadRow.id.desc()
                )
            else:
                query = query.order_by(
                    ChatKitThreadRow.created_at.asc(), ChatKitThreadRow.id.asc()
                )

            query = query.limit(limit + 1)
            result = await session.execute(query)
            rows = list(result.scalars().all())

            has_more = len(rows) > limit
            if has_more:
                rows = rows[:limit]

            threads = [_thread_from_row(r) for r in rows]
            last_id = rows[-1].id if rows else None

            return Page(data=threads, has_more=has_more, after=last_id)

    async def delete_thread(self, thread_id: str, context: RequestContext) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                row = await self._get_authorized_thread(session, thread_id, context)
                await session.delete(row)

    # ------------------------------------------------------------------
    # Item operations
    # ------------------------------------------------------------------

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await self._require_thread_owner(session, thread_id, context)
                item_json = item.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
                row = ChatKitItemRow(
                    id=item.id,
                    thread_id=thread_id,
                    item_type=item.type if hasattr(item, "type") else type(item).__name__,
                    item_json=item_json,
                    created_at=item.created_at if hasattr(item, "created_at") and item.created_at else _now(),
                )
                session.add(row)

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await self._require_thread_owner(session, thread_id, context)
                item_json = item.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
                existing = await session.get(ChatKitItemRow, item.id)
                if existing:
                    existing.item_json = item_json
                    existing.item_type = item.type if hasattr(item, "type") else type(item).__name__
                else:
                    row = ChatKitItemRow(
                        id=item.id,
                        thread_id=thread_id,
                        item_type=item.type if hasattr(item, "type") else type(item).__name__,
                        item_json=item_json,
                        created_at=item.created_at if hasattr(item, "created_at") and item.created_at else _now(),
                    )
                    session.add(row)

    async def load_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> ThreadItem:
        async with self._session_factory() as session:
            await self._require_thread_owner(session, thread_id, context)
            row = await session.get(ChatKitItemRow, item_id)
            if row is None or row.thread_id != thread_id:
                raise ValueError(f"Item {item_id} not found in thread {thread_id}")
            return _item_from_row(row)

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadItem]:
        async with self._session_factory() as session:
            await self._require_thread_owner(session, thread_id, context)

            query = select(ChatKitItemRow).where(
                ChatKitItemRow.thread_id == thread_id
            )

            if after:
                cursor_row = await session.get(ChatKitItemRow, after)
                if cursor_row:
                    if order == "desc":
                        query = query.where(
                            (ChatKitItemRow.created_at < cursor_row.created_at)
                            | (
                                (ChatKitItemRow.created_at == cursor_row.created_at)
                                & (ChatKitItemRow.id < cursor_row.id)
                            )
                        )
                    else:
                        query = query.where(
                            (ChatKitItemRow.created_at > cursor_row.created_at)
                            | (
                                (ChatKitItemRow.created_at == cursor_row.created_at)
                                & (ChatKitItemRow.id > cursor_row.id)
                            )
                        )

            if order == "desc":
                query = query.order_by(
                    ChatKitItemRow.created_at.desc(), ChatKitItemRow.id.desc()
                )
            else:
                query = query.order_by(
                    ChatKitItemRow.created_at.asc(), ChatKitItemRow.id.asc()
                )

            query = query.limit(limit + 1)
            result = await session.execute(query)
            rows = list(result.scalars().all())

            has_more = len(rows) > limit
            if has_more:
                rows = rows[:limit]

            items = [_item_from_row(r) for r in rows]
            last_id = rows[-1].id if rows else None

            return Page(data=items, has_more=has_more, after=last_id)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await self._require_thread_owner(session, thread_id, context)
                row = await session.get(ChatKitItemRow, item_id)
                if row and row.thread_id == thread_id:
                    await session.delete(row)

    # ------------------------------------------------------------------
    # Attachments (unsupported — explicit error)
    # ------------------------------------------------------------------

    async def save_attachment(
        self, attachment: Attachment, context: RequestContext
    ) -> None:
        raise NotImplementedError(
            "PostgreSQLStore does not support file attachments yet."
        )

    async def load_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> Attachment:
        raise NotImplementedError(
            "PostgreSQLStore does not support file attachments yet."
        )

    async def delete_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> None:
        raise NotImplementedError(
            "PostgreSQLStore does not support file attachments yet."
        )

    # ------------------------------------------------------------------
    # Legacy compatibility helpers (used by router during transition)
    # ------------------------------------------------------------------

    async def create_thread_legacy(self, metadata: dict) -> str:
        """Create a ChatKit thread and corresponding AgentRun for backward compat."""
        run_id = metadata.get("id") or metadata.get("run_id") or f"run-{uuid.uuid4()}"
        user_subject = metadata.get("user_subject", "user:local-dev")
        project_id = metadata.get("project_id")

        async with self._session_factory() as session:
            async with session.begin():
                # Create AgentRun for workflow tracking
                run = AgentRun(
                    id=run_id,
                    user_id=user_subject,
                    project_id=project_id if project_id and project_id.strip() else "",
                    repository_id=metadata.get("repository_id") or "",
                    task=metadata.get("task", ""),
                    status="CREATED",
                )
                session.add(run)

                # Create ChatKit thread
                thread_row = ChatKitThreadRow(
                    id=run_id,
                    user_subject=user_subject,
                    title=metadata.get("task", "New Chat")[:100],
                    status="active",
                    metadata_json={
                        "id": run_id,
                        "title": metadata.get("task", "New Chat")[:100],
                        "created_at": _now().isoformat(),
                    },
                    created_at=_now(),
                )
                session.add(thread_row)

        return run_id

    async def get_thread_by_project_id(self, project_id: str) -> dict | None:
        """Legacy: find latest run by project_id from agent_runs."""
        if not project_id or not project_id.strip():
            return None
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentRun)
                .where(AgentRun.project_id == project_id)
                .order_by(AgentRun.created_at.desc())
                .limit(1)
            )
            run = result.scalar_one_or_none()
            if run:
                return {"id": run.id, "run_id": run.id, "title": run.task[:100], "created_at": run.created_at}
        return None

    async def get_thread_legacy(self, run_id: str) -> dict | None:
        """Legacy: get thread info for a run_id."""
        async with self._session_factory() as session:
            row = await session.get(ChatKitThreadRow, run_id)
            if row:
                return {"id": row.id, "run_id": row.id, "title": row.title, "created_at": row.created_at}
            # Fallback to agent_runs
            result = await session.execute(select(AgentRun).where(AgentRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                return {"id": run.id, "run_id": run.id, "title": run.task[:100], "created_at": run.created_at}
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_authorized_thread(
        self, session: AsyncSession, thread_id: str, context: RequestContext
    ) -> ChatKitThreadRow:
        """Load thread and verify ownership. Raises ValueError if not found/unauthorized."""
        row = await session.get(ChatKitThreadRow, thread_id)
        if row is None:
            raise ValueError(f"Thread {thread_id} not found")
        self._verify_ownership(row, context)
        return row

    async def _require_thread_owner(
        self, session: AsyncSession, thread_id: str, context: RequestContext
    ) -> None:
        """Verify the user owns the thread without returning the row."""
        row = await session.get(ChatKitThreadRow, thread_id)
        if row is None:
            raise ValueError(f"Thread {thread_id} not found")
        self._verify_ownership(row, context)

    @staticmethod
    def _verify_ownership(row: ChatKitThreadRow, context: RequestContext) -> None:
        """Raise if user_subject does not match thread owner."""
        if row.user_subject != context.user_subject:
            raise ValueError(f"Thread {row.id} not found")
