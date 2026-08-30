"""Notifications router."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=50),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Notification.created_at.desc()).offset((page-1)*per_page).limit(per_page)
    notifs = (await db.execute(stmt)).scalars().all()
    unread_count = (await db.execute(
        select(func.count()).where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    )).scalar_one()
    return {
        "data": [{"id": str(n.id), "type": n.type, "title": n.title, "message": n.message,
                  "is_read": n.is_read, "entity_type": n.entity_type,
                  "entity_id": str(n.entity_id) if n.entity_id else None,
                  "created_at": n.created_at.isoformat()} for n in notifs],
        "meta": {"total": total, "page": page, "per_page": per_page, "unread_count": unread_count}
    }


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    n = (await db.execute(select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id))).scalar_one_or_none()
    if not n:
        raise NotFoundError("Notification not found.")
    n.is_read = True
    n.read_at = datetime.now(timezone.utc)
    db.add(n)
    return {"data": {"id": str(n.id), "is_read": n.is_read}}


@router.post("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    return {"message": "All notifications marked as read."}
