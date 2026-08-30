"""
Contact model — the central entity of the CRM.
Full-text search vector is maintained via PostgreSQL trigger.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.company import Company
    from app.models.campaign import Campaign, CampaignContact
    from app.models.call import Call
    from app.models.task import Task
    from app.models.note import ContactNote
    from app.models.opportunity import Opportunity
    from app.models.demo import Demo
    from app.models.recall import Recall
    from app.models.follow_up import FollowUp
    from app.models.no_answer import NoAnswerQueue


class ContactStatus(str, PyEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    IN_PROGRESS = "IN_PROGRESS"
    INTERESTED = "INTERESTED"
    EMAIL_REQUESTED = "EMAIL_REQUESTED"
    WHATSAPP_REQUESTED = "WHATSAPP_REQUESTED"
    DEMO_SCHEDULED = "DEMO_SCHEDULED"
    DEMO_DONE = "DEMO_DONE"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"
    NOT_INTERESTED = "NOT_INTERESTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    DUPLICATE = "DUPLICATE"
    RECALL_SCHEDULED = "RECALL_SCHEDULED"
    NO_ANSWER = "NO_ANSWER"
    UNASSIGNED = "UNASSIGNED"
    # Archive: contact is preserved but excluded from active working views
    ARCHIVED = "ARCHIVED"
    # Personal pool: Aseel distributed this lead to a specific user; awaiting their claim
    PENDING_CLAIM = "PENDING_CLAIM"


class ContactPriority(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Contact(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "contacts"

    # Identity
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Communication
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    normalized_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    secondary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 255 not 50: imported sheets occasionally carry free text here; PostgreSQL enforces the limit
    phone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    normalized_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    secondary_phone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Context
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ContactStatus.NEW, index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ContactPriority.MEDIUM
    )
    is_dnc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    # Activity tracking
    last_contact_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_contact_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    final_outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    archived_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    attempt_1: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    attempt_2: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    attempt_3: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Import tracking (Google Sheets idempotency)
    import_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    potential_duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )

    # Sheet-order — preserves the original xlsx row position (1 = first lead in sheet).
    # New contacts created via the app receive max(sheet_order)+1 so they always
    # appear at the END of the list, mirroring appending a row to the real Google Sheet.
    sheet_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Source Sheet tab from workbook (e.g. Leads, Ghaida fu, Amin fu, Demo, Oman Leads)
    source_sheet: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Full-text search vector
    search_vector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="contacts", foreign_keys=[company_id])
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id], back_populates="owned_contacts")
    archived_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[archived_by_id])
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", foreign_keys=[campaign_id])
    calls: Mapped[List["Call"]] = relationship("Call", back_populates="contact", order_by="Call.called_at.desc()")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="contact", order_by="Task.due_at.asc()")
    notes_history: Mapped[List["ContactNote"]] = relationship("ContactNote", back_populates="contact", foreign_keys="ContactNote.contact_id", order_by="ContactNote.created_at.desc()")
    opportunities: Mapped[List["Opportunity"]] = relationship("Opportunity", back_populates="contact")
    demos: Mapped[List["Demo"]] = relationship("Demo", back_populates="contact")
    recalls: Mapped[List["Recall"]] = relationship("Recall", back_populates="contact")
    follow_ups: Mapped[List["FollowUp"]] = relationship("FollowUp", back_populates="contact")
    no_answer_entries: Mapped[List["NoAnswerQueue"]] = relationship("NoAnswerQueue", back_populates="contact")
    potential_duplicate_of: Mapped[Optional["Contact"]] = relationship("Contact", foreign_keys=[potential_duplicate_of_id], remote_side="Contact.id")
    campaign_contacts: Mapped[List["CampaignContact"]] = relationship("CampaignContact", back_populates="contact")

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    __table_args__ = (
        Index("idx_contacts_owner_status", "owner_id", "status"),
        Index("idx_contacts_country_industry", "country", "industry"),
    )
