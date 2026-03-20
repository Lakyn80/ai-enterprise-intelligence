"""assistant traces

Revision ID: 002
Revises: 001
Create Date: 2026-03-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_traces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("assistant_type", sa.String(length=32), nullable=False),
        sa.Column("request_kind", sa.String(length=16), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=True),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cache_source", sa.String(length=64), nullable=True),
        sa.Column("cache_strategy", sa.String(length=64), nullable=True),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id"),
    )
    op.create_index("ix_assistant_traces_trace_id", "assistant_traces", ["trace_id"])
    op.create_index("ix_assistant_traces_assistant_type", "assistant_traces", ["assistant_type"])
    op.create_index("ix_assistant_traces_request_kind", "assistant_traces", ["request_kind"])
    op.create_index("ix_assistant_traces_status", "assistant_traces", ["status"])

    op.create_table(
        "assistant_trace_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_pk", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["trace_pk"], ["assistant_traces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_trace_steps_trace_pk", "assistant_trace_steps", ["trace_pk"])
    op.create_index("ix_assistant_trace_steps_step_name", "assistant_trace_steps", ["step_name"])


def downgrade() -> None:
    op.drop_index("ix_assistant_trace_steps_step_name", table_name="assistant_trace_steps")
    op.drop_index("ix_assistant_trace_steps_trace_pk", table_name="assistant_trace_steps")
    op.drop_table("assistant_trace_steps")
    op.drop_index("ix_assistant_traces_status", table_name="assistant_traces")
    op.drop_index("ix_assistant_traces_request_kind", table_name="assistant_traces")
    op.drop_index("ix_assistant_traces_assistant_type", table_name="assistant_traces")
    op.drop_index("ix_assistant_traces_trace_id", table_name="assistant_traces")
    op.drop_table("assistant_traces")
