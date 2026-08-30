"""
Authentication service — login, logout, token refresh, account lockout.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountLockedError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_password_hash,
    hash_password,
    normalize_email,
    verify_password,
)
from app.models.user import User
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
LOCKOUT_HARD_ATTEMPTS = 10


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(
        self, email: str, password: str, ip_address: str = ""
    ) -> tuple[str, str, User]:
        """
        Authenticate user. Returns (access_token, refresh_token, user).
        Raises UnauthorizedError on bad credentials (same error for both cases — no user enumeration).
        Raises AccountLockedError if account is locked.
        """
        normalized = normalize_email(email)
        stmt = (
            select(User)
            .where(User.normalized_email == normalized, User.deleted_at.is_(None))
            .options(selectinload(User.team))
        )
        result = await self.db.execute(stmt)
        user: Optional[User] = result.scalar_one_or_none()

        # Timing-safe: run a real bcrypt verification even when the email is unknown,
        # so response time never reveals which emails exist.
        candidate_hash = user.password_hash if user else dummy_password_hash()
        password_ok = verify_password(password, candidate_hash)

        if not user or not password_ok:
            if user:
                await self._record_failed_attempt(user)
            logger.warning("auth.login_failed", email=email, ip=ip_address)
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            logger.warning("auth.inactive_user", user_id=str(user.id))
            raise UnauthorizedError("Account is inactive. Please contact your administrator.")

        if user.is_locked:
            if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
                raise AccountLockedError(
                    f"Account locked until {user.locked_until.strftime('%H:%M UTC')}."
                )
            else:
                # Lockout expired — reset
                await self._reset_login_attempts(user)

        # Successful login
        await self._on_successful_login(user, ip_address)

        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        logger.info("auth.login_success", user_id=str(user.id), role=user.role)
        return access_token, refresh_token, user

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, User]:
        """Validate refresh token and issue new access token."""
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = uuid.UUID(payload["sub"])

        stmt = select(User).where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None)).options(selectinload(User.team))
        result = await self.db.execute(stmt)
        user: Optional[User] = result.scalar_one_or_none()

        if not user:
            raise UnauthorizedError("User not found or inactive.")

        access_token = create_access_token(user.id, user.role)
        return access_token, user

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None)).options(selectinload(User.team))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        self.db.add(user)
        logger.info("auth.password_changed", user_id=str(user.id))

    async def _record_failed_attempt(self, user: User) -> None:
        user.login_attempts = (user.login_attempts or 0) + 1
        if user.login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.is_locked = True
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            logger.warning("auth.account_locked", user_id=str(user.id), attempts=user.login_attempts)
        self.db.add(user)
        await self.db.flush()

    async def _reset_login_attempts(self, user: User) -> None:
        user.login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        self.db.add(user)
        await self.db.flush()

    async def _on_successful_login(self, user: User, ip_address: str) -> None:
        user.login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        self.db.add(user)
        await self.db.flush()
