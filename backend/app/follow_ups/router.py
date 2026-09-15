"""
Follow-ups router — Demo follow-ups and Communication follow-ups with team-wide manager filters.

Req 9: contact_id is now optional — a follow-up may be created for a company that does
not yet exist as a Contact in the CRM. company_name_snapshot preserves the free-text name.
meeting_with records the client-side contact person name.
demo_id links back to a source Demo when created via conversion.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.contact import Contact
from app.models.company import Company
from app.models.follow_up import FollowUp
from app.models.user import User
from app.audit.service import AuditService
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter(prefix="/follow-ups", tags=["Follow-ups"])


class FollowUpCreateBody(BaseModel):
    # contact_id is optional — follow-up can be for a company without a CRM contact
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    company_name_snapshot: Optional[str] = None  # free-text company name (req 9)
    meeting_with: Optional[str] = None            # client-side contact person (req 9)
    user_id: Optional[str] = None
    demo_id: Optional[str] = None                 # source Demo when converting (req 9)
    type: str = "GENERAL"
    due_at: Optional[str] = None                  # nullable for historical/undated follow-ups
    notes: Optional[str] = None
    next_step: Optional[str] = None
    status: str = "PENDING"


class FollowUpUpdateBody(BaseModel):
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    company_name_snapshot: Optional[str] = None
    meeting_with: Optional[str] = None
    user_id: Optional[str] = None
    type: Optional[str] = None
    due_at: Optional[str] = None
    notes: Optional[str] = None
    next_step: Optional[str] = None
    status: Optional[str] = None


def _fu_dict(f: FollowUp) -> dict:
    # Derive best display company name: canonical company > snapshot > contact's company
    company_name = None
    if f.company and f.company.name:
        company_name = f.company.name
    elif f.company_name_snapshot:
        company_name = f.company_name_snapshot
    elif f.contact and f.contact.company:
        company_name = f.contact.company.name

    # Owner name: explicit user > contact's owner
    owner_name = None
    if f.user:
        owner_name = f.user.full_name
    elif f.contact and f.contact.owner:
        owner_name = f.contact.owner.full_name

    return {
        "id": str(f.id),
        "contact_id": str(f.contact_id) if f.contact_id else None,
        "contact_name": f.contact.full_name if f.contact else None,
        "phone": f.contact.phone if f.contact else None,
        "email": f.contact.email if f.contact else None,
        "company_id": str(f.company_id) if f.company_id else None,
        "company_name": company_name,
        "company_name_snapshot": f.company_name_snapshot,
        "meeting_with": f.meeting_with,
        "demo_id": str(f.demo_id) if f.demo_id else None,
        "user_id": str(f.user_id) if f.user_id else None,
        "owner_name": owner_name,
        "type": f.type,
        "section": "DEMO" if f.type == "DEMO" else "COMMUNICATION",
        "status": f.status,
        "due_at": f.due_at.isoformat() if f.due_at else None,
        "completed_at": f.completed_at.isoformat() if f.completed_at else None,
        "notes": f.notes,
        "next_step": f.next_step,
        "created_at": f.created_at.isoformat(),
    }


def _base_fu_query():
    return select(FollowUp).options(
        selectinload(FollowUp.contact).selectinload(Contact.company),
        selectinload(FollowUp.contact).selectinload(Contact.owner),
        selectinload(FollowUp.company),
        selectinload(FollowUp.user),
    )


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
    stmt = _base_fu_query()
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
        stmt = stmt.where(FollowUp.company_id == uuid.UUID(company_id))
    if overdue_only:
        stmt = stmt.where(FollowUp.due_at < datetime.now(timezone.utc), FollowUp.status == "PENDING")

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(FollowUp.due_at.asc().nullslast()).offset((page - 1) * per_page).limit(per_page)
    items = (await db.execute(stmt)).scalars().all()
    return {
        "data": [_fu_dict(f) for f in items],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }


@router.post("", status_code=201)
async def create_follow_up(
    body: FollowUpCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_user = uuid.UUID(body.user_id) if body.user_id else current_user.id

    # Resolve company_name_snapshot: if company_id given, use the company name
    company_name_snapshot = body.company_name_snapshot
    if body.company_id and not company_name_snapshot:
        company = (await db.get(Company, uuid.UUID(body.company_id)))
        if company:
            company_name_snapshot = company.name

    due_at = datetime.fromisoformat(body.due_at) if body.due_at else None

    fu = FollowUp(
        contact_id=uuid.UUID(body.contact_id) if body.contact_id else None,
        company_id=uuid.UUID(body.company_id) if body.company_id else None,
        company_name_snapshot=company_name_snapshot,
        meeting_with=body.meeting_with,
        user_id=target_user,
        demo_id=uuid.UUID(body.demo_id) if body.demo_id else None,
        type=body.type,
        status=body.status,
        due_at=due_at,
        notes=body.notes,
        next_step=body.next_step,
    )
    db.add(fu)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="follow_up.created",
        entity_type="follow_up",
        actor_id=current_user.id,
        entity_id=fu.id,
        new_value={
            "type": fu.type,
            "contact_id": str(fu.contact_id) if fu.contact_id else None,
            "company_name_snapshot": fu.company_name_snapshot,
            "demo_id": str(fu.demo_id) if fu.demo_id else None,
        },
    )

    # Re-fetch with relationships
    stmt = _base_fu_query().where(FollowUp.id == fu.id)
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _fu_dict(loaded)}


@router.get("/{follow_up_id}")
async def get_follow_up(
    follow_up_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = _base_fu_query().where(FollowUp.id == follow_up_id)
    fu = (await db.execute(stmt)).scalar_one_or_none()
    if not fu:
        raise NotFoundError("Follow-up not found.")
    if not current_user.is_manager_or_above and str(fu.user_id) != str(current_user.id):
        raise ForbiddenError("Access denied.")
    return {"data": _fu_dict(fu)}


@router.patch("/{follow_up_id}")
async def update_follow_up(
    follow_up_id: uuid.UUID,
    body: FollowUpUpdateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = _base_fu_query().where(FollowUp.id == follow_up_id)
    fu = (await db.execute(stmt)).scalar_one_or_none()
    if not fu:
        raise NotFoundError("Follow-up not found.")
    if not current_user.is_manager_or_above and str(fu.user_id) != str(current_user.id):
        raise ForbiddenError("Access denied.")

    if body.contact_id is not None:
        fu.contact_id = uuid.UUID(body.contact_id) if body.contact_id else None
    if body.company_id is not None:
        fu.company_id = uuid.UUID(body.company_id) if body.company_id else None
    if body.company_name_snapshot is not None:
        fu.company_name_snapshot = body.company_name_snapshot
    if body.meeting_with is not None:
        fu.meeting_with = body.meeting_with
    if body.user_id is not None:
        fu.user_id = uuid.UUID(body.user_id) if body.user_id else None
    if body.type is not None:
        fu.type = body.type
    if body.status is not None:
        fu.status = body.status
    if body.due_at is not None:
        fu.due_at = datetime.fromisoformat(body.due_at) if body.due_at else None
    if body.notes is not None:
        fu.notes = body.notes
    if body.next_step is not None:
        fu.next_step = body.next_step

    db.add(fu)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="follow_up.updated",
        entity_type="follow_up",
        actor_id=current_user.id,
        entity_id=fu.id,
        new_value={"status": fu.status, "company_name_snapshot": fu.company_name_snapshot},
    )

    reloaded = (await db.execute(stmt)).scalar_one()
    return {"data": _fu_dict(reloaded)}


@router.post("/{follow_up_id}/complete")
async def complete_follow_up(
    follow_up_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = _base_fu_query().where(FollowUp.id == follow_up_id)
    fu = (await db.execute(stmt)).scalar_one_or_none()
    if not fu:
        raise NotFoundError("Follow-up not found.")
    if not current_user.is_manager_or_above and str(fu.user_id) != str(current_user.id):
        raise ForbiddenError("Access denied.")

    fu.status = "COMPLETED"
    fu.completed_at = datetime.now(timezone.utc)
    db.add(fu)
    await db.flush()
    return {"data": _fu_dict(fu)}
