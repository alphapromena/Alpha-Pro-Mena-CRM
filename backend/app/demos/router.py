"""
Demos router — stage tracking, scheduling, notes, and team-wide filters for managers.
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
from app.models.demo import Demo, DemoStage
from app.models.contact import Contact
from app.models.company import Company
from app.models.user import User
from app.models.audit import AuditLog
from app.audit.service import AuditService
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/demos", tags=["Demos"])


def _demo_dict(d: Demo) -> dict:
    return {
        "id": str(d.id),
        "contact_id": str(d.contact_id),
        "contact_name": d.contact.full_name if d.contact else None,
        "contact_phone": d.contact.phone if d.contact else None,
        "contact_email": d.contact.email if d.contact else None,
        "company_id": str(d.company_id) if d.company_id else None,
        "company_name": d.company.name if d.company else (d.contact.company.name if (d.contact and d.contact.company) else None),
        "owner_id": str(d.owner_id) if d.owner_id else None,
        "owner_name": d.owner.full_name if d.owner else None,
        "stage": d.stage,
        "scheduled_at": d.scheduled_at.isoformat() if d.scheduled_at else None,
        "completed_at": d.completed_at.isoformat() if d.completed_at else None,
        "notes": d.notes,
        "result": d.result,
        "created_at": d.created_at.isoformat(),
    }


@router.get("")
async def list_demos(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    stage: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Demo).options(
        selectinload(Demo.contact).selectinload(Contact.company),
        selectinload(Demo.company),
        selectinload(Demo.owner),
    )
    target_user = owner_id or user_id
    if not current_user.is_manager_or_above:
        stmt = stmt.where(Demo.owner_id == current_user.id)
    elif target_user:
        stmt = stmt.where(Demo.owner_id == uuid.UUID(target_user))

    if stage:
        if stage == "AGREED":
            stmt = stmt.where(Demo.stage.in_(["REQUESTED", "SCHEDULED"]))
        else:
            stmt = stmt.where(Demo.stage == stage)
    if company_id:
        stmt = stmt.where(Demo.company_id == uuid.UUID(company_id))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Demo.scheduled_at.asc().nullslast(), Demo.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    demos = (await db.execute(stmt)).scalars().all()
    return {"data": [_demo_dict(d) for d in demos], "meta": {"total": total, "page": page, "per_page": per_page}}


@router.post("", status_code=201)
async def create_demo(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_owner = uuid.UUID(body["owner_id"]) if body.get("owner_id") else current_user.id
    demo = Demo(
        contact_id=uuid.UUID(body["contact_id"]),
        company_id=uuid.UUID(body["company_id"]) if body.get("company_id") else None,
        owner_id=target_owner,
        stage=body.get("stage", DemoStage.REQUESTED),
        scheduled_at=datetime.fromisoformat(body["scheduled_at"]) if body.get("scheduled_at") else None,
        notes=body.get("notes"),
        result=body.get("result"),
    )
    db.add(demo)
    await db.flush()

    # Re-fetch
    stmt = select(Demo).where(Demo.id == demo.id).options(
        selectinload(Demo.contact).selectinload(Contact.company),
        selectinload(Demo.company),
        selectinload(Demo.owner),
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _demo_dict(loaded)}


@router.patch("/{demo_id}")
async def update_demo(
    demo_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Demo).where(Demo.id == demo_id).options(
        selectinload(Demo.contact).selectinload(Contact.company),
        selectinload(Demo.company),
        selectinload(Demo.owner),
    )
    demo = (await db.execute(stmt)).scalar_one_or_none()
    if not demo:
        raise NotFoundError("Demo not found.")

    old_stage = demo.stage
    for field in ["stage", "notes", "result"]:
        if field in body and body[field] is not None:
            setattr(demo, field, body[field])
    if "scheduled_at" in body:
        demo.scheduled_at = datetime.fromisoformat(body["scheduled_at"]) if body["scheduled_at"] else None
    if "owner_id" in body and body["owner_id"]:
        demo.owner_id = uuid.UUID(body["owner_id"])
    if body.get("stage") == "COMPLETED" and not demo.completed_at:
        demo.completed_at = datetime.now(timezone.utc)

    db.add(demo)
    await db.flush()

    # Audit log if stage changed
    if "stage" in body and body["stage"] != old_stage:
        audit = AuditService(db)
        await audit.log(
            action="demo.stage_changed",
            entity_type="demo",
            actor_id=current_user.id,
            entity_id=demo.id,
            old_value={"stage": old_stage},
            new_value={"stage": demo.stage, "result": demo.result},
        )

    reloaded = (await db.execute(stmt)).scalar_one()
    return {"data": _demo_dict(reloaded)}
