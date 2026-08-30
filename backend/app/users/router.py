"""
Users router — user management for Team Leads and Managers.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_team_lead, require_manager_or_above
from app.database import get_db
from app.models.user import User
from app.users.schemas import UserCreateRequest, UserListResponse, UserResponse, UserUpdateRequest
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def _user_to_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "role": user.role,
        "team_id": str(user.team_id) if user.team_id else None,
        "team_name": user.team.name if user.team else None,
        "is_active": user.is_active,
        "is_locked": user.is_locked,
        "lead_capacity": user.lead_capacity,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
    }


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    users, total = await service.list_users(
        page=page, per_page=per_page, search=search,
        role=role, team_id=team_id, is_active=is_active, actor=current_user,
    )
    return {
        "data": [_user_to_response(u) for u in users],
        "meta": {"total": total, "page": page, "per_page": per_page, "total_pages": -(-total // per_page)},
    }


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreateRequest,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.create_user(body.model_dump(), actor=current_user)
    return _user_to_response(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.get_user(user_id)
    return _user_to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.update_user(user_id, body.model_dump(exclude_unset=True), actor=current_user)
    return _user_to_response(user)


@router.post("/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.disable_user(user_id, actor=current_user)
    return _user_to_response(user)


@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.update_user(user_id, {"is_active": True}, actor=current_user)
    return _user_to_response(user)
