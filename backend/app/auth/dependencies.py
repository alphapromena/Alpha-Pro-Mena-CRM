"""
Auth dependencies — FastAPI injectable dependencies for current user and role checks.
These are used as Depends() in every protected endpoint.
"""
import uuid
from typing import Optional

import structlog
from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthService
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)

# Cookie names
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


async def get_current_user(
    request: Request,
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from the JWT access token cookie.
    Binds user context to structured logging.
    """
    # Prioritize explicit Authorization header if provided, otherwise fallback to cookie
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    else:
        token = access_token

    if not token:
        raise UnauthorizedError("Authentication required.")

    payload = decode_token(token, expected_type="access")
    user_id = uuid.UUID(payload["sub"])

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise UnauthorizedError("User not found or inactive.")

    # Bind user context for all subsequent log calls in this request
    structlog.contextvars.bind_contextvars(
        user_id=str(user.id),
        user_role=user.role,
    )

    return user


def require_roles(*roles: UserRole):
    """
    FastAPI dependency factory — enforces that the current user has one of the given roles.
    This is the ROUTE-LAYER check. Service-layer checks are also mandatory.
    """
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in [r.value if isinstance(r, UserRole) else r for r in roles]:
            raise ForbiddenError(
                f"This action requires one of the following roles: {', '.join(str(r) for r in roles)}."
            )
        return current_user
    return _checker


# Convenient pre-built dependency aliases
require_team_lead = require_roles(UserRole.TEAM_LEAD, "TEAM_LEAD", "ADMIN", "TEAM_LEADER")
require_manager_or_above = require_roles(UserRole.TEAM_LEAD, UserRole.MANAGER, "TEAM_LEAD", "MANAGER", "ADMIN", "TEAM_LEADER")
require_data_ops_or_above = require_roles(UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.DATA_OPS, "TEAM_LEAD", "MANAGER", "DATA_OPS", "ADMIN", "TEAM_LEADER")
require_user_or_above = require_roles(UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.USER, "TEAM_LEAD", "MANAGER", "USER", "ADMIN", "SALES_USER", "TEAM_LEADER")

# Backward compatibility aliases
require_admin = require_team_lead
require_team_leader_or_above = require_team_lead
