"""Teams router."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth.dependencies import get_current_user, require_admin, require_manager_or_above
from app.database import get_db
from app.models.user import User, Team
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("")
async def list_teams(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Team).where(Team.deleted_at.is_(None)).options(selectinload(Team.members), selectinload(Team.manager))
    count = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Team.name).offset((page-1)*per_page).limit(per_page)
    teams = (await db.execute(stmt)).scalars().all()
    return {
        "data": [{"id": str(t.id), "name": t.name, "description": t.description,
                  "manager_id": str(t.manager_id) if t.manager_id else None,
                  "manager_name": t.manager.full_name if t.manager else None,
                  "member_count": len(t.members), "created_at": t.created_at.isoformat()} for t in teams],
        "meta": {"total": count, "page": page, "per_page": per_page}
    }


@router.post("", status_code=201)
async def create_team(
    body: dict,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    team = Team(
        name=body["name"],
        description=body.get("description"),
        manager_id=uuid.UUID(body["manager_id"]) if body.get("manager_id") else None,
    )
    db.add(team)
    await db.flush()
    return {"id": str(team.id), "name": team.name, "created_at": team.created_at.isoformat()}


@router.get("/{team_id}")
async def get_team(
    team_id: uuid.UUID,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Team).where(Team.id == team_id, Team.deleted_at.is_(None)).options(selectinload(Team.members), selectinload(Team.manager))
    team = (await db.execute(stmt)).scalar_one_or_none()
    if not team:
        raise NotFoundError("Team not found.")
    return {"id": str(team.id), "name": team.name, "description": team.description,
            "manager": {"id": str(team.manager.id), "name": team.manager.full_name} if team.manager else None,
            "members": [{"id": str(m.id), "name": m.full_name, "role": m.role} for m in team.members]}


@router.patch("/{team_id}")
async def update_team(
    team_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))
    team = (await db.execute(stmt)).scalar_one_or_none()
    if not team:
        raise NotFoundError("Team not found.")
    if "name" in body:
        team.name = body["name"]
    if "description" in body:
        team.description = body["description"]
    if "manager_id" in body:
        team.manager_id = uuid.UUID(body["manager_id"]) if body["manager_id"] else None
    db.add(team)
    return {"id": str(team.id), "name": team.name}
