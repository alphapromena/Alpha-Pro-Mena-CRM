"""
Follow-up model — structured follow-ups after activities.

contact_id is nullable (req 9): a follow-up may be recorded for a
company that does not yet exist as a Contact in the CRM. In that case
company_name_snapshot holds the free-text company name.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.company import Company
    from app.models.user import User
    from app.models.task import Task
    from app.models.demo import Demo


class FollowUpType(str, PyEnum):
    CALL = "CALL"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    DEMO = "DEMO"
    MEETING = "MEETING"
    PROPOSAL = "PROPOSAL"
    GENERAL = "GENERAL"


class FollowUp(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "follow_ups"

    # contact_id is now nullable so a follow-up can be created without
    # a CRM Contact when the company is unknown / not yet imported.
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Free-text snapshot of the company name at the time of creation.
    # Preserved even if the linked Company is later renamed or removed.
    company_name_snapshot: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # The person the meeting/follow-up is with (client side)
    meeting_with: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    # Link to the source Demo when created via Demo → Follow-up conversion
    demo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("demos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False, default=FollowUpType.GENERAL, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source workbook auditability
    source_sheet: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_row: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="follow_ups")
    company: Mapped[Optional["Company"]] = relationship("Company")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    task: Mapped[Optional["Task"]] = relationship("Task", foreign_keys=[task_id])
    source_demo: Mapped[Optional["Demo"]] = relationship("Demo", foreign_keys=[demo_id])
