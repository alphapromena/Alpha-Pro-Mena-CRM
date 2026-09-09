"""
Demo model — product demonstration appointments.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.company import Company
    from app.models.user import User


class DemoStage(str, PyEnum):
    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
    RESCHEDULED = "RESCHEDULED"


class DemoStatus(str, PyEnum):
    INTERESTED_NEXT_STEP = "INTERESTED_NEXT_STEP"
    NOT_INTERESTED = "NOT_INTERESTED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"
    PENDING = "PENDING"


class DemoReportStatus(str, PyEnum):
    REPORT_COMPLETE = "REPORT_COMPLETE"
    NEEDS_REPORT = "NEEDS_REPORT"


class Demo(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "demos"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default=DemoStage.REQUESTED, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=DemoStatus.PENDING, index=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Detailed Demo Report & Presentation Details
    presenter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attendees: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics_covered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_step_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Report completion badge: REPORT_COMPLETE | NEEDS_REPORT
    report_status: Mapped[str] = mapped_column(String(30), nullable=False, default=DemoReportStatus.NEEDS_REPORT, index=True)

    # Historical Tracking (demos conducted prior to CRM rollout)
    is_historical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    historical_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    historical_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Ownership & Audit actor IDs
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", back_populates="demos")
    company: Mapped[Optional["Company"]] = relationship("Company")
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id])
    updated_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by_id])

    __table_args__ = (
        Index("idx_demos_owner_status", "owner_id", "status"),
        Index("idx_demos_report_status", "report_status"),
        Index("idx_demos_is_historical", "is_historical"),
    )
