"""Remaining domain routers — follow-ups, recalls, no-answer, demos, opportunities, campaigns, notifications, audit, automation, search, reports, admin, google-sheets."""

# ── Follow-ups ──────────────────────────────────────────────────────────────
# follow_ups/router.py
follow_ups_content = '''"""Follow-ups router."""
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
from app.models.follow_up import FollowUp
from app.models.user import User
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/follow-ups", tags=["Follow-ups"])

@router.get("")
async def list_follow_ups(
    page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None), type: Optional[str] = Query(None),
    overdue_only: bool = Query(False),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(FollowUp).options(selectinload(FollowUp.contact))
    if not current_user.is_manager_or_above:
        stmt = stmt.where(FollowUp.user_id == current_user.id)
    if status: stmt = stmt.where(FollowUp.status == status)
    if type: stmt = stmt.where(FollowUp.type == type)
    if overdue_only: stmt = stmt.where(FollowUp.due_at < datetime.now(timezone.utc), FollowUp.status == "PENDING")
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(FollowUp.due_at.asc()).offset((page-1)*per_page).limit(per_page)
    items = (await db.execute(stmt)).scalars().all()
    return {"data": [{"id": str(f.id), "contact_id": str(f.contact_id), "contact_name": f.contact.full_name if f.contact else None, "type": f.type, "status": f.status, "due_at": f.due_at.isoformat(), "notes": f.notes} for f in items], "meta": {"total": total, "page": page, "per_page": per_page}}

@router.post("", status_code=201)
async def create_follow_up(body: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fu = FollowUp(contact_id=uuid.UUID(body["contact_id"]), user_id=current_user.id, type=body.get("type", "GENERAL"), status="PENDING", due_at=datetime.fromisoformat(body["due_at"]), notes=body.get("notes"))
    db.add(fu); await db.flush()
    return {"data": {"id": str(fu.id), "type": fu.type, "status": fu.status, "due_at": fu.due_at.isoformat()}}

@router.post("/{follow_up_id}/complete")
async def complete_follow_up(follow_up_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fu = (await db.execute(select(FollowUp).where(FollowUp.id == follow_up_id))).scalar_one_or_none()
    if not fu: raise NotFoundError("Follow-up not found.")
    fu.status = "COMPLETED"; fu.completed_at = datetime.now(timezone.utc)
    db.add(fu)
    return {"data": {"id": str(fu.id), "status": fu.status}}
'''

print("follow_ups content ready")
