"""
Follow-ups router — Demo follow-ups and Communication follow-ups with team-wide manager filters.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.contact import Contact
from app.models.company import Company
from app.models.follow_up import FollowUp
from app.models.user import User
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/follow-ups", tags=["Follow-ups"])


@router.get("")
async def list_follow_ups(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    overdue_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FollowUp).options(
        selectinload(FollowUp.contact).selectinload(Contact.company),
        selectinload(FollowUp.contact).selectinload(Contact.owner),
        selectinload(FollowUp.user),
    )
    if not current_user.is_manager_or_above:
        stmt = stmt.where(FollowUp.user_id == current_user.id)
    elif user_id:
        stmt = stmt.where(FollowUp.user_id == uuid.UUID(user_id))

    if status:
        stmt = stmt.where(FollowUp.status == status)
    if type:
        stmt = stmt.where(FollowUp.type == type)
    if section == "DEMO":
        stmt = stmt.where(FollowUp.type == "DEMO")
    elif section == "COMMUNICATION":
        stmt = stmt.where(FollowUp.type.in_(["CALL", "EMAIL", "WHATSAPP", "GENERAL", "PROPOSAL", "MEETING"]))
    if company_id:
        stmt = stmt.join(Contact, FollowUp.contact_id == Contact.id).where(Contact.company_id == uuid.UUID(company_id))
    if overdue_only:
        stmt = stmt.where(FollowUp.due_at < datetime.now(timezone.utc), FollowUp.status == "PENDING")

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(FollowUp.due_at.asc()).offset((page - 1) * per_page).limit(per_page)
    items = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            {
                "id": str(f.id),
                "contact_id": str(f.contact_id),
                "contact_name": f.contact.full_name if f.contact else None,
                "company_name": f.contact.company.name if (f.contact and f.contact.company) else None,
                "phone": f.contact.phone if f.contact else None,
                "email": f.contact.email if f.contact else None,
                "user_id": str(f.user_id) if f.user_id else None,
                "owner_name": f.user.full_name if f.user else (f.contact.owner.full_name if (f.contact and f.contact.owner) else None),
                "type": f.type,
                "section": "DEMO" if f.type == "DEMO" else "COMMUNICATION",
                "status": f.status,
                "due_at": f.due_at.isoformat(),
                "notes": f.notes,
            }
            for f in items
        ],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }


@router.post("", status_code=201)
async def create_follow_up(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_user = uuid.UUID(body["user_id"]) if body.get("user_id") else current_user.id
    fu = FollowUp(
        contact_id=uuid.UUID(body["contact_id"]),
        user_id=target_user,
        type=body.get("type", "GENERAL"),
        status="PENDING",
        due_at=datetime.fromisoformat(body["due_at"]),
        notes=body.get("notes"),
    )
    db.add(fu)
    await db.flush()
    return {"data": {"id": str(fu.id), "type": fu.type, "status": fu.status, "due_at": fu.due_at.isoformat()}}


@router.post("/{follow_up_id}/complete")
async def complete_follow_up(
    follow_up_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fu = (await db.execute(select(FollowUp).where(FollowUp.id == follow_up_id))).scalar_one_or_none()
    if not fu:
        raise NotFoundError("Follow-up not found.")
    fu.status = "COMPLETED"
    fu.completed_at = datetime.now(timezone.utc)
    db.add(fu)
    await db.flush()
    return {"data": {"id": str(fu.id), "status": fu.status}}
