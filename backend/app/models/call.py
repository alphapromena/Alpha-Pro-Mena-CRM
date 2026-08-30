"""
Call model — every call attempt is recorded.
Outcomes are configurable by admin.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.user import User


class CallOutcome(str, PyEnum):
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    CALL_LATER = "CALL_LATER"
    INTERESTED = "INTERESTED"
    EMAIL_REQUESTED = "EMAIL_REQUESTED"
    WHATSAPP_REQUESTED = "WHATSAPP_REQUESTED"
    DEMO_REQUESTED = "DEMO_REQUESTED"
    MEETING_REQUESTED = "MEETING_REQUESTED"
    PROPOSAL_REQUESTED = "PROPOSAL_REQUESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    WRONG_NUMBER = "WRONG_NUMBER"
    LEFT_COMPANY = "LEFT_COMPANY"
    COMPETITOR = "COMPETITOR"
    NEED_APPROVAL = "NEED_APPROVAL"
    CONVERTED = "CONVERTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    VOICEMAIL = "VOICEMAIL"
    ANSWERED = "ANSWERED"
    OTHER = "OTHER"


class Call(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "calls"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    attempt_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # For call_later / recalls — when the customer requested callback
    callback_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    previous_outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    correction_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    corrected_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", back_populates="calls")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    corrected_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[corrected_by_id])
