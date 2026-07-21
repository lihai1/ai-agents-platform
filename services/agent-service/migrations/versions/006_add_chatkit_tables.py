"""Add ChatKit persistence tables.

Revision ID: 006
Revises: 005
Create Date: 2025-07-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chatkit_threads",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_subject", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_chatkit_threads_user", "chatkit_threads", ["user_subject"])
    op.create_index(
        "idx_chatkit_threads_created",
        "chatkit_threads",
        [sa.text("created_at DESC")],
    )

    op.create_table(
        "chatkit_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(),
            sa.ForeignKey("chatkit_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("item_json", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_chatkit_items_thread", "chatkit_items", ["thread_id"])
    op.create_index(
        "idx_chatkit_items_thread_created",
        "chatkit_items",
        ["thread_id", "created_at", "id"],
    )

    op.create_table(
        "chatkit_input_routes",
        sa.Column("item_id", sa.String(), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(),
            sa.ForeignKey("chatkit_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("terminal_session_id", sa.String(), nullable=True),
        sa.Column("allowed_values_json", JSONB, nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("idx_input_routes_thread", "chatkit_input_routes", ["thread_id"])
    op.create_index("idx_input_routes_run", "chatkit_input_routes", ["run_id"])
    op.create_index("idx_input_routes_status", "chatkit_input_routes", ["status"])
    op.create_index(
        "idx_input_routes_correlation", "chatkit_input_routes", ["correlation_id"]
    )


def downgrade() -> None:
    op.drop_table("chatkit_input_routes")
    op.drop_table("chatkit_items")
    op.drop_table("chatkit_threads")
