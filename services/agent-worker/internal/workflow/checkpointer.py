from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from internal.config import settings

# Module-level checkpointer instance
_checkpointer = None
_pool = None


def _normalize_db_url(url: str) -> str:
    """Convert SQLAlchemy asyncpg URL to a plain PostgreSQL URL for psycopg."""
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    if url.startswith("postgres://") and not url.startswith("postgresql://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


async def get_checkpointer() -> AsyncPostgresSaver:
    """Get or create async Postgres checkpointer backed by a psycopg connection pool."""
    global _checkpointer, _pool
    if _checkpointer is None:
        db_url = _normalize_db_url(settings.database_url)
        # Use a small async connection pool; kwargs are passed to psycopg.AsyncConnection.connect.
        # autocommit=True allows AsyncPostgresSaver.setup() to run DDL such as
        # CREATE INDEX CONCURRENTLY outside a transaction block.
        _pool = AsyncConnectionPool(
            db_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=False,
        )
        await _pool.open()
        _checkpointer = AsyncPostgresSaver(_pool)
        await _checkpointer.setup()
    return _checkpointer
