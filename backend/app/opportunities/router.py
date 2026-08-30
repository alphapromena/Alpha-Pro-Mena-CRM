"""
Opportunities router — pipeline management and sequential company journey roadmaps.
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
from app.models.opportunity import Opportunity, OpportunityRoadmapStep, OpportunityStage
from app.models.contact import Contact
from app.models.company import Company
from app.models.user import User
from app.models.audit import AuditLog
from app.audit.service import AuditService
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


def _step_dict(s: OpportunityRoadmapStep) -> dict:
    return {
        "id": str(s.id),
        "company_id": str(s.company_id),
        "opportunity_id": str(s.opportunity_id) if s.opportunity_id else None,
        "contact_id": str(s.contact_id) if s.contact_id else None,
        "contact_name": s.contact.full_name if s.contact else None,
        "user_id": str(s.user_id) if s.user_id else None,
        "user_name": s.user.full_name if s.user else "Sales Agent",
        "step_type": s.step_type,
        "step_date": s.step_date.isoformat(),
        "notes": s.notes,
        "status": s.status,
        "step_order": s.step_order,
        "created_at": s.created_at.isoformat(),
    }


@router.get("/roadmap/{company_id}")
async def get_company_roadmap(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sequential roadmap steps for a given company."""
    stmt = (
        select(OpportunityRoadmapStep)
        .where(OpportunityRoadmapStep.company_id == company_id)
        .options(
            selectinload(OpportunityRoadmapStep.contact),
            selectinload(OpportunityRoadmapStep.user),
        )
        .order_by(OpportunityRoadmapStep.step_order.asc(), OpportunityRoadmapStep.step_date.asc())
    )
    steps = (await db.execute(stmt)).scalars().all()
    return {"data": [_step_dict(s) for s in steps]}


@router.post("/roadmap/{company_id}", status_code=201)
async def create_roadmap_step(
    company_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a sequential journey step to a company's roadmap."""
    count_stmt = select(func.count(OpportunityRoadmapStep.id)).where(OpportunityRoadmapStep.company_id == company_id)
    step_count = (await db.execute(count_stmt)).scalar_one()

    step_dt = datetime.fromisoformat(body["step_date"]) if body.get("step_date") else datetime.now(timezone.utc)
    target_user = uuid.UUID(body["user_id"]) if body.get("user_id") else current_user.id
    step = OpportunityRoadmapStep(
        company_id=company_id,
        opportunity_id=uuid.UUID(body["opportunity_id"]) if body.get("opportunity_id") else None,
        contact_id=uuid.UUID(body["contact_id"]) if body.get("contact_id") else None,
        user_id=target_user,
        step_type=body.get("step_type", "First Call"),
        step_date=step_dt,
        notes=body.get("notes"),
        status=body.get("status", "COMPLETED"),
        step_order=body.get("step_order", step_count + 1),
    )
    db.add(step)
    await db.flush()

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action="opportunity.roadmap_step_created",
        entity_type="opportunity_roadmap",
        actor_id=current_user.id,
        entity_id=step.id,
        new_value={"company_id": str(company_id), "step_type": step.step_type, "status": step.status},
    )

    # Re-fetch with relationships
    stmt = (
        select(OpportunityRoadmapStep)
        .where(OpportunityRoadmapStep.id == step.id)
        .options(selectinload(OpportunityRoadmapStep.contact), selectinload(OpportunityRoadmapStep.user))
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _step_dict(loaded)}


@router.patch("/roadmap/steps/{step_id}")
async def update_roadmap_step(
    step_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing roadmap step."""
    stmt = (
        select(OpportunityRoadmapStep)
        .where(OpportunityRoadmapStep.id == step_id)
        .options(selectinload(OpportunityRoadmapStep.contact), selectinload(OpportunityRoadmapStep.user))
    )
    step = (await db.execute(stmt)).scalar_one_or_none()
    if not step:
        raise NotFoundError("Roadmap step not found.")

    for field in ["step_type", "notes", "status", "step_order"]:
        if field in body and body[field] is not None:
            setattr(step, field, body[field])
    if "step_date" in body and body["step_date"]:
        step.step_date = datetime.fromisoformat(body["step_date"])
    if "contact_id" in body:
        step.contact_id = uuid.UUID(body["contact_id"]) if body["contact_id"] else None

    db.add(step)
    await db.flush()
    return {"data": _step_dict(step)}


@router.delete("/roadmap/steps/{step_id}", status_code=204)
async def delete_roadmap_step(
    step_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a roadmap step."""
    stmt = select(OpportunityRoadmapStep).where(OpportunityRoadmapStep.id == step_id)
    step = (await db.execute(stmt)).scalar_one_or_none()
    if step:
        await db.delete(step)


def _opp_dict(o: Opportunity) -> dict:
    return {
        "id": str(o.id),
        "title": o.title,
        "contact_id": str(o.contact_id) if o.contact_id else None,
        "contact_name": o.contact.full_name if o.contact else None,
        "company_id": str(o.company_id) if o.company_id else None,
        "company_name": o.company.name if o.company else None,
        "owner_id": str(o.owner_id) if o.owner_id else None,
        "owner_name": o.owner.full_name if o.owner else "Sales Agent",
        "value": o.value or 0.0,
        "stage": o.stage,
        "probability": o.probability,
        "expected_close_at": o.expected_close_at.isoformat() if o.expected_close_at else None,
        "lost_reason": o.lost_reason,
        "created_at": o.created_at.isoformat(),
    }


@router.get("")
async def list_opportunities(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    stage: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Opportunity)
        .where(Opportunity.deleted_at.is_(None))
        .options(selectinload(Opportunity.contact), selectinload(Opportunity.company), selectinload(Opportunity.owner))
    )
    target_user = owner_id or user_id
    if not current_user.is_manager_or_above:
        stmt = stmt.where(Opportunity.owner_id == current_user.id)
    elif target_user:
        stmt = stmt.where(Opportunity.owner_id == uuid.UUID(target_user))

    if stage:
        stmt = stmt.where(Opportunity.stage == stage)
    if company_id:
        stmt = stmt.where(Opportunity.company_id == uuid.UUID(company_id))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Opportunity.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    opps = (await db.execute(stmt)).scalars().all()
    return {"data": [_opp_dict(o) for o in opps], "meta": {"total": total, "page": page, "per_page": per_page}}


@router.post("", status_code=201)
async def create_opportunity(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_owner = uuid.UUID(body["owner_id"]) if body.get("owner_id") else current_user.id
    opp = Opportunity(
        title=body["title"],
        contact_id=uuid.UUID(body["contact_id"]) if body.get("contact_id") else None,
        company_id=uuid.UUID(body["company_id"]) if body.get("company_id") else None,
        owner_id=target_owner,
        value=body.get("value"),
        stage=body.get("stage", OpportunityStage.NEW),
        probability=body.get("probability"),
        expected_close_at=datetime.fromisoformat(body["expected_close_at"]) if body.get("expected_close_at") else None,
    )
    db.add(opp)
    await db.flush()

    # Re-fetch
    stmt = select(Opportunity).where(Opportunity.id == opp.id).options(
        selectinload(Opportunity.contact), selectinload(Opportunity.company), selectinload(Opportunity.owner)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _opp_dict(loaded)}


@router.patch("/{opp_id}")
async def update_opportunity(
    opp_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Opportunity).where(Opportunity.id == opp_id, Opportunity.deleted_at.is_(None)).options(
        selectinload(Opportunity.contact), selectinload(Opportunity.company), selectinload(Opportunity.owner)
    )
    opp = (await db.execute(stmt)).scalar_one_or_none()
    if not opp:
        raise NotFoundError("Opportunity not found.")

    old_stage = opp.stage
    for field in ["title", "stage", "value", "probability", "lost_reason"]:
        if field in body and body[field] is not None:
            setattr(opp, field, body[field])
    if "expected_close_at" in body:
        opp.expected_close_at = datetime.fromisoformat(body["expected_close_at"]) if body["expected_close_at"] else None
    if "owner_id" in body and body["owner_id"]:
        opp.owner_id = uuid.UUID(body["owner_id"])
    if opp.stage in [OpportunityStage.WON, OpportunityStage.LOST] and not opp.closed_at:
        opp.closed_at = datetime.now(timezone.utc)

    db.add(opp)
    await db.flush()

    # Audit log if stage changed
    if "stage" in body and body["stage"] != old_stage:
        audit = AuditService(db)
        await audit.log(
            action="opportunity.stage_changed",
            entity_type="opportunity",
            actor_id=current_user.id,
            entity_id=opp.id,
            old_value={"stage": old_stage},
            new_value={"stage": opp.stage, "value": opp.value},
        )

    reloaded = (await db.execute(stmt)).scalar_one()
    return {"data": _opp_dict(reloaded)}
