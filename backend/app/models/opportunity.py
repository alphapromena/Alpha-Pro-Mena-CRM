"""
Opportunity model — sales pipeline management.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.company import Company
    from app.models.user import User
    from app.models.note import Note


class OpportunityStage(str, PyEnum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    DEMO = "DEMO"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class Opportunity(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "opportunities"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default=OpportunityStage.NEW, index=True)
    probability: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100
    expected_close_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="opportunities")
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="opportunities")
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
    roadmap_steps: Mapped[List["OpportunityRoadmapStep"]] = relationship("OpportunityRoadmapStep", back_populates="opportunity", order_by="OpportunityRoadmapStep.step_order.asc()")


class OpportunityRoadmapStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "opportunity_roadmap_steps"

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    step_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "First Call", "Email Sent", "Demo Agreed", "Demo Completed", "Proposal Sent", "Latest Status"
    step_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="COMPLETED")  # COMPLETED | IN_PROGRESS | PENDING
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    company: Mapped["Company"] = relationship("Company")
    opportunity: Mapped[Optional["Opportunity"]] = relationship("Opportunity", back_populates="roadmap_steps")
    contact: Mapped[Optional["Contact"]] = relationship("Contact")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
