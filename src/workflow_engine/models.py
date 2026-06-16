"""SQLAlchemy models for workflow runs and step executions.

These map onto the ``shared_core.database.Base`` metadata so alembic and the
shared ``DatabaseManager`` pick them up automatically.
"""

from shared_core.database import Base, TimestampMixin, UUIDMixin
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON


class WorkflowRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_runs"

    workflow_name = Column(String(255), nullable=False)
    yaml_definition = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Quarantined failed steps (the dead-letter queue) serialized as JSON.
    dead_letters = Column(JSON, nullable=True)

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
