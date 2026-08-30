"""Campaigns router."""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from app.auth.dependencies import get_current_user, require_manager_or_above
from app.database import get_db
from app.models.campaign import Campaign, CampaignStatus
from app.models.user import User
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.get("")
async def list_campaigns(
    page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Campaign).where(Campaign.deleted_at.is_(None)).options(selectinload(Campaign.owner))
    if status:
        stmt = stmt.where(Campaign.status == status)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Campaign.created_at.desc()).offset((page-1)*per_page).limit(per_page)
    campaigns = (await db.execute(stmt)).scalars().all()
    return {
        "data": [{"id": str(c.id), "name": c.name, "description": c.description,
                  "status": c.status, "target_country": c.target_country, "target_industry": c.target_industry,
                  "owner_id": str(c.owner_id) if c.owner_id else None,
                  "start_at": c.start_at.isoformat() if c.start_at else None,
                  "end_at": c.end_at.isoformat() if c.end_at else None,
                  "created_at": c.created_at.isoformat()} for c in campaigns],
        "meta": {"total": total, "page": page, "per_page": per_page}
    }


@router.post("", status_code=201)
async def create_campaign(
    body: dict, current_user: User = Depends(require_manager_or_above), db: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    c = Campaign(
        name=body["name"], description=body.get("description"),
        status=CampaignStatus.ACTIVE,
        target_country=body.get("target_country"), target_industry=body.get("target_industry"),
        owner_id=current_user.id,
        start_at=datetime.fromisoformat(body["start_at"]) if body.get("start_at") else None,
        end_at=datetime.fromisoformat(body["end_at"]) if body.get("end_at") else None,
    )
    db.add(c)
    await db.flush()
    return {"data": {"id": str(c.id), "name": c.name, "status": c.status}}


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.deleted_at.is_(None)).options(selectinload(Campaign.owner)))).scalar_one_or_none()
    if not c:
        raise NotFoundError("Campaign not found.")
    return {"data": {"id": str(c.id), "name": c.name, "description": c.description, "status": c.status,
                     "target_country": c.target_country, "target_industry": c.target_industry,
                     "created_at": c.created_at.isoformat()}}
