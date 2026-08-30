"""
No-answer queue router — retry cadence (48h / 7d) with team-wide manager filters.
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
from app.models.no_answer import NoAnswerQueue
from app.models.contact import Contact
from app.models.company import Company
from app.models.user import User

router = APIRouter(prefix="/no-answer", tags=["No Answer Queue"])


@router.get("")
async def list_no_answer(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    attempt_number: Optional[int] = Query(None),
    contact_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    overdue_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NoAnswerQueue).options(
        selectinload(NoAnswerQueue.contact).selectinload(Contact.company),
        selectinload(NoAnswerQueue.user),
    )
    if not current_user.is_manager_or_above:
        stmt = stmt.where(NoAnswerQueue.user_id == current_user.id)
    elif user_id:
        stmt = stmt.where(NoAnswerQueue.user_id == uuid.UUID(user_id))

    if contact_id:
        stmt = stmt.where(NoAnswerQueue.contact_id == uuid.UUID(contact_id))
    if status:
        stmt = stmt.where(NoAnswerQueue.status == status)
    if attempt_number:
        stmt = stmt.where(NoAnswerQueue.attempt_number == attempt_number)

    if company_id or country:
        stmt = stmt.join(Contact, NoAnswerQueue.contact_id == Contact.id)
        if company_id:
            stmt = stmt.where(Contact.company_id == uuid.UUID(company_id))
        if country:
            stmt = stmt.where(Contact.country.ilike(f"%{country}%"))

    now = datetime.now(timezone.utc)
    if overdue_only:
        stmt = stmt.where(NoAnswerQueue.next_attempt_at < now, NoAnswerQueue.status == "PENDING")

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(NoAnswerQueue.next_attempt_at.asc()).offset((page - 1) * per_page).limit(per_page)
    items = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            {
                "id": str(q.id),
                "contact_id": str(q.contact_id),
                "contact_name": q.contact.full_name if q.contact else None,
                "phone": q.contact.phone if q.contact else None,
                "country": q.contact.country if q.contact else None,
                "company_name": q.contact.company.name if (q.contact and q.contact.company) else None,
                "user_id": str(q.user_id) if q.user_id else None,
                "user_name": q.user.full_name if q.user else "Sales Agent",
                "attempt_number": q.attempt_number,
                "previous_result": q.contact.last_outcome or "No Answer" if q.contact else "No Answer",
                "notes": q.contact.notes if q.contact else None,
                "last_attempt_at": q.last_attempt_at.isoformat() if q.last_attempt_at else None,
                "next_attempt_at": q.next_attempt_at.isoformat() if q.next_attempt_at else None,
                "is_overdue": (
                    (q.next_attempt_at.replace(tzinfo=timezone.utc) if q.next_attempt_at.tzinfo is None else q.next_attempt_at) < now
                ) if q.next_attempt_at else False,
                "status": q.status,
            }
            for q in items
        ],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }
