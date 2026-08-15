"""SQLAlchemy models for workflow runs and step executions.

These map onto the vendored ``Base`` metadata so Alembic and the local
``DatabaseManager`` pick them up automatically.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from workflow_engine.internal.vendor_core.database import (
    Base,
    TimestampMixin,
    UUIDMixin,
)


class WorkflowRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_runs"

    workflow_name = Column(String(255), nullable=False)
    yaml_definition = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Quarantined failed steps (the dead-letter queue) serialized as JSON.
    dead_letters = Column(JSON, nullable=True)
    version_hash = Column(String(64), nullable=True, index=True)

    steps = relationship(
        "StepExecution", back_populates="run", cascade="all, delete-orphan"
    )


class StepExecution(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "step_executions"

    run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=False)
    step_id = Column(String(255), nullable=False)
    task_name = Column(String(255), nullable=False)
    status = Column(String(50), default="PENDING")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    attempt = Column(Integer, default=0)

    run = relationship("WorkflowRun", back_populates="steps")


class ScheduleRecord(Base, TimestampMixin):
    """Durable schedule state, usable by API and Celery processes alike."""

    __tablename__ = "schedules"

    name = Column(String(255), primary_key=True)
    cron = Column(String(255), nullable=False)
    yaml_definition = Column(Text, nullable=False)
    last_run = Column(DateTime(timezone=True), nullable=True)
    next_run = Column(DateTime(timezone=True), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)


class WebhookRegistration(Base, TimestampMixin):
    """Persisted webhook definition; the optional secret is never listed."""

    __tablename__ = "webhook_registrations"

    name = Column(String(255), primary_key=True)
    yaml_definition = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    secret = Column(Text, nullable=True)


class WorkflowDefinition(Base, TimestampMixin):
    """A canonical YAML version pinned by its deterministic content hash."""

    __tablename__ = "workflow_definitions"

    content_hash = Column(String(64), primary_key=True)
    yaml_definition = Column(Text, nullable=False)


class IdempotencyRecord(Base, TimestampMixin):
    """One durable claim per namespace/key pair."""

    __tablename__ = "idempotency_records"

    namespace = Column(String(255), primary_key=True)
    key = Column(String(255), primary_key=True)


class ExecutionEventRecord(Base, UUIDMixin, TimestampMixin):
    """Ordered execution events retained as additive dashboard metadata."""

    __tablename__ = "execution_events"

    run_id = Column(String(36), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    kind = Column(String(100), nullable=False)
    trigger_id = Column(String(36), nullable=True)
    step_id = Column(String(255), nullable=True)
    attempt = Column(Integer, nullable=True)
    details = Column(JSON, nullable=False, default=dict)
