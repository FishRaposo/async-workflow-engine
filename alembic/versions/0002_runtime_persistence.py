"""Persist Task 3 runtime services and pinned workflow metadata.

Revision ID: 0002_runtime_persistence
Revises: 0001_initial
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002_runtime_persistence"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_runs", sa.Column("version_hash", sa.String(64), nullable=True)
    )
    op.create_index("ix_workflow_runs_version_hash", "workflow_runs", ["version_hash"])
    op.create_table(
        "schedules",
        sa.Column("name", sa.String(255), primary_key=True),
        sa.Column("cron", sa.String(255), nullable=False),
        sa.Column("yaml_definition", sa.Text(), nullable=False),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "webhook_registrations",
        sa.Column("name", sa.String(255), primary_key=True),
        sa.Column("yaml_definition", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("secret", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_definitions",
        sa.Column("content_hash", sa.String(64), primary_key=True),
        sa.Column("yaml_definition", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "idempotency_records",
        sa.Column("namespace", sa.String(255), primary_key=True),
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "execution_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("trigger_id", sa.String(36), nullable=True),
        sa.Column("step_id", sa.String(255), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_execution_events_run_id", "execution_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_events_run_id", table_name="execution_events")
    op.drop_table("execution_events")
    op.drop_table("idempotency_records")
    op.drop_table("workflow_definitions")
    op.drop_table("webhook_registrations")
    op.drop_table("schedules")
    op.drop_index("ix_workflow_runs_version_hash", table_name="workflow_runs")
    op.drop_column("workflow_runs", "version_hash")
