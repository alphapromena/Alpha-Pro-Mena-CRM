"""Calls router — log and query call attempts."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.auth.dependencies import get_current_user
from app.contacts.service import ContactService
from app.database import get_db
from app.models.call import Call
from app.models.contact import Contact
from app.models.user import User
from app.core.exceptions import DNCError, NotFoundError, ForbiddenError
from app.automation.service import AutomationService

router = APIRouter(prefix="/calls", tags=["Calls"])


class LogCallBody(BaseModel):
    contact_id: str
    outcome: str
    notes: Optional[str] = None
    duration_seconds: Optional[int] = None
    called_at: Optional[str] = None  # ISO datetime; defaults to now
    callback_requested_at: Optional[str] = None


@router.post("", status_code=201)
async def log_call(
    body: LogCallBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log a call attempt. Triggers automation rules based on outcome."""
    contact_service = ContactService(db)
    contact = await contact_service.get_contact(uuid.UUID(body.contact_id), current_user)

    if contact.is_dnc:
        raise DNCError()

    called_at = (
        datetime.fromisoformat(body.called_at) if body.called_at
        else datetime.now(timezone.utc)
    )

    call = Call(
        contact_id=contact.id,
        user_id=current_user.id,
        outcome=body.outcome,
        notes=body.notes,
        duration_seconds=body.duration_seconds,
        called_at=called_at,
        callback_requested_at=datetime.fromisoformat(body.callback_requested_at) if body.callback_requested_at else None,
    )
    db.add(call)

    # Update contact last_contact_at, attempt_count, and last_outcome
    contact.attempt_count = (contact.attempt_count or 0) + 1
    contact.last_outcome = body.outcome
    contact.last_contact_at = called_at
    db.add(contact)
    await db.flush()

    # Fire automation engine
    automation_svc = AutomationService(db)
    await automation_svc.fire_event(
        event=f"call.outcome.{body.outcome.lower()}",
        entity_id=contact.id,
        entity_type="contact",
        payload={
            "call_id": str(call.id),
            "contact_id": str(contact.id),
            "owner_id": str(contact.owner_id) if contact.owner_id else None,
            "outcome": body.outcome,
            "user_id": str(current_user.id),
        },
        actor_id=current_user.id,
    )

    return {
        "data": {
            "id": str(call.id),
            "contact_id": str(call.contact_id),
            "outcome": call.outcome,
            "notes": call.notes,
            "called_at": call.called_at.isoformat(),
            "created_at": call.created_at.isoformat(),
        }
    }


@router.get("")
async def list_calls(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    contact_id: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Call).options(selectinload(Call.contact), selectinload(Call.user))

    # Scope: sales users only see their own calls
    if not current_user.is_manager_or_above:
        stmt = stmt.where(Call.user_id == current_user.id)

    if contact_id:
        stmt = stmt.where(Call.contact_id == uuid.UUID(contact_id))
    if outcome:
        stmt = stmt.where(Call.outcome == outcome)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Call.called_at.desc()).offset((page-1)*per_page).limit(per_page)
    calls = (await db.execute(stmt)).scalars().all()

    return {
        "data": [{
            "id": str(c.id),
            "contact_id": str(c.contact_id),
            "contact_name": c.contact.full_name if c.contact else None,
            "user_id": str(c.user_id) if c.user_id else None,
            "outcome": c.outcome,
            "notes": c.notes,
            "duration_seconds": c.duration_seconds,
            "called_at": c.called_at.isoformat(),
        } for c in calls],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }
