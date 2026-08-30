"""
Users service — CRUD, role management, capacity.
"""
import uuid
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import AuditService
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import hash_password, normalize_email
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        role: Optional[str] = None,
        team_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        actor: Optional[User] = None,
    ) -> Tuple[List[User], int]:
        stmt = select(User).where(User.deleted_at.is_(None)).options(selectinload(User.team))

        if search:
            q = f"%{search}%"
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    User.first_name.ilike(q),
                    User.last_name.ilike(q),
                    User.email.ilike(q),
                )
            )
        if role:
            stmt = stmt.where(User.role == role)
        if team_id:
            stmt = stmt.where(User.team_id == uuid.UUID(team_id))
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(User.first_name.asc()).offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(stmt)
        return result.scalars().all(), total

    async def get_user(self, user_id: uuid.UUID) -> User:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None)).options(selectinload(User.team))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User not found.")
        return user

    async def create_user(self, data: dict, actor: User) -> User:
        if not actor.is_manager_or_above:
            raise ForbiddenError("Only Managers and Team Leads can create users.")

        # Managers cannot create TEAM_LEAD accounts — only Team Leads can.
        requested_role = data.get("role", UserRole.USER)
        if requested_role in (UserRole.TEAM_LEAD, "TEAM_LEAD", "ADMIN", "TEAM_LEADER") and not actor.is_team_lead:
            raise ForbiddenError("Only Team Leads can create Team Lead accounts.")

        # Check email uniqueness
        normalized = normalize_email(data["email"])
        existing = await self.db.execute(
            select(User).where(User.normalized_email == normalized)
        )
        if existing.scalar_one_or_none():
            raise ConflictError("A user with this email already exists.")

        team_id = uuid.UUID(data["team_id"]) if data.get("team_id") else None
        role_val = data.get("role", UserRole.USER)
        if role_val in ("ADMIN", "TEAM_LEADER"):
            role_val = UserRole.TEAM_LEAD
        elif role_val == "SALES_USER":
            role_val = UserRole.USER

        user = User(
            email=data["email"],
            normalized_email=normalized,
            first_name=data["first_name"],
            last_name=data["last_name"],
            password_hash=hash_password(data["password"]),
            role=role_val,
            team_id=team_id,
            lead_capacity=data.get("lead_capacity", 500),
        )
        self.db.add(user)
        await self.db.flush()

        await self.audit.log(
            action="user.created",
            entity_type="user",
            actor_id=actor.id,
            entity_id=user.id,
            new_value={"email": user.email, "role": user.role},
        )
        return user

    async def update_user(self, user_id: uuid.UUID, data: dict, actor: User) -> User:
        if not actor.is_manager_or_above:
            raise ForbiddenError("Only Managers and Team Leads can update users.")

        # Managers cannot promote users to TEAM_LEAD — only Team Leads can.
        if "role" in data and data["role"] in (UserRole.TEAM_LEAD, "TEAM_LEAD", "ADMIN", "TEAM_LEADER") and not actor.is_team_lead:
            raise ForbiddenError("Only Team Leads can assign the Team Lead role.")

        user = await self.get_user(user_id)
        old = {"role": user.role, "is_active": user.is_active, "team_id": str(user.team_id) if user.team_id else None}

        # Prevent team lead from demoting themselves
        if str(user.id) == str(actor.id) and "role" in data and data["role"] not in (UserRole.TEAM_LEAD, "TEAM_LEAD", "ADMIN"):
            raise ForbiddenError("Team Leads cannot demote themselves.")

        for field in ["first_name", "last_name", "is_active", "lead_capacity"]:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])

        if "role" in data and data["role"] is not None:
            r = data["role"]
            if r in ("ADMIN", "TEAM_LEADER"):
                r = UserRole.TEAM_LEAD
            elif r == "SALES_USER":
                r = UserRole.USER
            user.role = r

        if "team_id" in data:
            user.team_id = uuid.UUID(data["team_id"]) if data["team_id"] else None

        self.db.add(user)
        await self.db.flush()

        await self.audit.log(
            action="user.updated",
            entity_type="user",
            actor_id=actor.id,
            entity_id=user.id,
            old_value=old,
            new_value={"role": user.role, "is_active": user.is_active},
        )
        return user

    async def disable_user(self, user_id: uuid.UUID, actor: User) -> User:
        user = await self.update_user(user_id, {"is_active": False}, actor)
        await self.audit.log(
            action="user.disabled",
            entity_type="user",
            actor_id=actor.id,
            entity_id=user.id,
        )
        return user
