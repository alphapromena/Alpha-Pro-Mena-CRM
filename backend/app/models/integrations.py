"""
Google Sheets sync configuration and run tracking models.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.campaign import Campaign
    from app.models.contact import Contact


class GoogleSheetsSyncConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "google_sheets_sync_configs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    spreadsheet_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Sheet1")
    range: Mapped[str] = mapped_column(String(50), nullable=False, default="A:Z")
    column_mapping: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # e.g. {"first_name": "A", "last_name": "B", "email": "C", "phone": "D", ...}
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_every_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_row_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    sync_runs: Mapped[list["GoogleSheetsSyncRun"]] = relationship("GoogleSheetsSyncRun", back_populates="config")


class GoogleSheetsSyncRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "google_sheets_sync_runs"

    config_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("google_sheets_sync_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    # RUNNING | COMPLETED | FAILED | CANCELLED
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduler")
    # scheduler | manual
    triggered_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    config: Mapped[GoogleSheetsSyncConfig] = relationship("GoogleSheetsSyncConfig", back_populates="sync_runs")
    errors: Mapped[list["SyncErrorLog"]] = relationship("SyncErrorLog", back_populates="sync_run")


class SyncErrorLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sync_error_log"

    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("google_sheets_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sync_run: Mapped[GoogleSheetsSyncRun] = relationship("GoogleSheetsSyncRun", back_populates="errors")


class LeadDistributionRule(UUIDMixin, TimestampMixin, Base):
    """Admin-configurable lead distribution rules."""
    __tablename__ = "lead_distribution_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # MANUAL | ROUND_ROBIN | PERCENTAGE | COUNTRY | INDUSTRY
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign")


class LeadAssignment(UUIDMixin, TimestampMixin, Base):
    """History of every lead assignment change."""
    __tablename__ = "lead_assignments"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    previous_owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact: Mapped[Optional["Contact"]] = relationship("Contact")


class SavedFilter(UUIDMixin, TimestampMixin, Base):
    """User-saved search/filter configurations."""
    __tablename__ = "saved_filters"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filter_config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped["User"] = relationship("User")
