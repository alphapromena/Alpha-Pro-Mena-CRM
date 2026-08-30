"""Audit logs router — read-only, manager+ only."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth.dependencies import require_manager_or_above
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("")
async def list_audit_logs(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100),
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).options(selectinload(AuditLog.actor))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page-1)*per_page).limit(per_page)
    logs = (await db.execute(stmt)).scalars().all()
    return {
        "data": [{
            "id": str(l.id),
            "actor_name": l.actor.full_name if l.actor else "System",
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": str(l.entity_id) if l.entity_id else None,
            "old_value": l.old_value, "new_value": l.new_value,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat(),
        } for l in logs],
        "meta": {"total": total, "page": page, "per_page": per_page}
    }
