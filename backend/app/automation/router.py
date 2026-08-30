"""Automation rules router — admin configuration of rule engine."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.automation import AutomationRule
from app.models.user import User
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/automation", tags=["Automation"])


@router.get("/rules")
async def list_rules(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    stmt = select(AutomationRule)
    if is_active is not None:
        stmt = stmt.where(AutomationRule.is_active == is_active)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(AutomationRule.trigger_event).offset((page-1)*per_page).limit(per_page)
    rules = (await db.execute(stmt)).scalars().all()
    return {
        "data": [{"id": str(r.id), "name": r.name, "description": r.description,
                  "trigger_event": r.trigger_event, "action_type": r.action_type,
                  "action_config": r.action_config, "conditions": r.conditions,
                  "delay_minutes": r.delay_minutes, "is_active": r.is_active,
                  "created_at": r.created_at.isoformat()} for r in rules],
        "meta": {"total": total, "page": page, "per_page": per_page}
    }


@router.post("/rules", status_code=201)
async def create_rule(
    body: dict, current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    rule = AutomationRule(
        name=body["name"], description=body.get("description"),
        trigger_event=body["trigger_event"], conditions=body.get("conditions"),
        action_type=body["action_type"], action_config=body["action_config"],
        delay_minutes=body.get("delay_minutes", 0), is_active=body.get("is_active", True),
        created_by=current_user.id,
    )
    db.add(rule)
    await db.flush()
    return {"data": {"id": str(rule.id), "name": rule.name, "trigger_event": rule.trigger_event}}


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID, body: dict,
    current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    rule = (await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise NotFoundError("Rule not found.")
    for field in ["name", "description", "is_active", "action_config", "conditions", "delay_minutes"]:
        if field in body:
            setattr(rule, field, body[field])
    db.add(rule)
    return {"data": {"id": str(rule.id), "name": rule.name, "is_active": rule.is_active}}
