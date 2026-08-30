"""
Recalls router — scheduled call-backs with team-wide manager filters.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.recall import Recall
from app.models.contact import Contact
from app.models.company import Company
from app.models.user import User
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/recalls", tags=["Recalls"])


def _recall_dict(r: Recall) -> dict:
    return {
        "id": str(r.id),
        "contact_id": str(r.contact_id),
        "contact_name": r.contact.full_name if r.contact else None,
        "phone": r.contact.phone if r.contact else None,
        "company_name": r.contact.company.name if (r.contact and r.contact.company) else None,
        "user_id": str(r.user_id) if r.user_id else None,
        "user_name": r.user.full_name if r.user else "Sales Agent",
        "attempt_number": r.contact.attempt_count if r.contact else 1,
        "previous_result": r.contact.last_outcome or "Re Call" if r.contact else "Re Call",
        "scheduled_at": r.scheduled_at.isoformat(),
        "status": r.status,
        "notes": r.notes,
        "created_at": r.created_at.isoformat(),
    }


@router.get("")
async def list_recalls(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    contact_id: Optional[str] = Query(None),
    upcoming_only: bool = Query(False),
    overdue_only: bool = Query(False),
    today_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Recall).options(
        selectinload(Recall.contact).selectinload(Contact.company),
        selectinload(Recall.user),
    )
    if not current_user.is_manager_or_above:
        stmt = stmt.where(Recall.user_id == current_user.id)
    elif user_id:
        stmt = stmt.where(Recall.user_id == uuid.UUID(user_id))

    if contact_id:
        stmt = stmt.where(Recall.contact_id == uuid.UUID(contact_id))
    if company_id:
        stmt = stmt.join(Contact, Recall.contact_id == Contact.id).where(Contact.company_id == uuid.UUID(company_id))

    now = datetime.now(timezone.utc)
    if status:
        stmt = stmt.where(Recall.status == status)
    if upcoming_only:
        stmt = stmt.where(Recall.scheduled_at >= now, Recall.status == "PENDING")
    if overdue_only:
        stmt = stmt.where(Recall.scheduled_at < now, Recall.status == "PENDING")
    if today_only:
        today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
        today_end = today_start + timedelta(days=1)
        stmt = stmt.where(Recall.scheduled_at.between(today_start, today_end))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Recall.scheduled_at.asc()).offset((page - 1) * per_page).limit(per_page)
    recalls = (await db.execute(stmt)).scalars().all()
    return {"data": [_recall_dict(r) for r in recalls], "meta": {"total": total, "page": page, "per_page": per_page}}


@router.post("", status_code=201)
async def create_recall(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_user = uuid.UUID(body["user_id"]) if body.get("user_id") else current_user.id
    recall = Recall(
        contact_id=uuid.UUID(body["contact_id"]),
        user_id=target_user,
        scheduled_at=datetime.fromisoformat(body["scheduled_at"]),
        notes=body.get("notes"),
        status="PENDING",
    )
    db.add(recall)
    await db.flush()

    # Re-fetch
    stmt = select(Recall).where(Recall.id == recall.id).options(
        selectinload(Recall.contact).selectinload(Contact.company), selectinload(Recall.user)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _recall_dict(loaded)}


@router.post("/{recall_id}/complete")
async def complete_recall(
    recall_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recall = (await db.execute(select(Recall).where(Recall.id == recall_id))).scalar_one_or_none()
    if not recall:
        raise NotFoundError("Recall not found.")
    recall.status = "COMPLETED"
    recall.completed_at = datetime.now(timezone.utc)
    db.add(recall)
    await db.flush()
    return {"data": {"id": str(recall.id), "status": recall.status}}
