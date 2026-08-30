"""
Task model — the primary work unit for sales users.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.company import Company
    from app.models.user import User


class TaskType(str, PyEnum):
    CALL = "CALL"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    RECALL = "RECALL"
    FOLLOW_UP = "FOLLOW_UP"
    DEMO = "DEMO"
    MEETING = "MEETING"
    PROPOSAL = "PROPOSAL"
    OTHER = "OTHER"


class TaskStatus(str, PyEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class TaskPriority(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False, default=TaskType.CALL, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskPriority.MEDIUM)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.OPEN, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    automation_rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("automation_rules.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="tasks")
    company: Mapped[Optional["Company"]] = relationship("Company")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_tasks")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
