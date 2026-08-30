"""
ContactNote model — multi-record timestamped note history for contacts.
"""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.user import User


class ContactNote(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "contact_notes"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", back_populates="notes_history")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


# Alias for compatibility
Note = ContactNote
