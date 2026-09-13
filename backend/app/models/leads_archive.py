"""
LeadsArchive model — permanent historical archive for the workbook 'Leads' worksheet.

The Leads worksheet contains thousands of historical and unassigned records that must
never be imported as active contacts, but must be permanently preserved with 100%
data fidelity for audit, historical demo/follow-up reconciliation, and rollback.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDMixin


class LeadsArchive(UUIDMixin, Base):
    __tablename__ = "leads_archive"

    batch_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sheet_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Leads", index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Full raw row preserved as JSON
    raw_data: Mapped[str] = mapped_column(Text, nullable=False)

    # Core indexed fields for historical search and cross-referencing
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    salesperson: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Audit & integrity
    row_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
