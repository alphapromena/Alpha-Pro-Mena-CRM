"""
Authentication service — login, logout, token refresh, account lockout,
email verification, forced password activation, and password reset.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountLockedError,
    EmailDeliveryError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_password_hash,
    generate_secure_token,
    hash_password,
    hash_token,
    normalize_email,
    validate_company_email,
    validate_password_strength,
    verify_password,
    verify_token_hash,
)
from app.core.email import send_verification_email, send_password_reset_email
from app.models.user import User
from app.models.audit import AuditLog
from app.audit.service import AuditService
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
LOCKOUT_HARD_ATTEMPTS = 10


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def login(
        self, email: str, password: str, ip_address: str = ""
    ) -> tuple[str, str, User]:
        """
        Authenticate user. Returns (access_token, refresh_token, user).
        Raises UnauthorizedError on bad credentials (timing-safe; prevents user enumeration).
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

        # Timing-safe: run a real bcrypt verification even when the email is unknown
        candidate_hash = user.password_hash if user else dummy_password_hash()
        password_ok = verify_password(password, candidate_hash)

        if not user or not password_ok:
            if user:
                await self._record_failed_attempt(user)
            await self.audit.log(
                action="user.login_failed",
                entity_type="user",
                actor_id=user.id if user else None,
                ip_address=ip_address,
                notes=f"Failed login attempt for {normalized}",
            )
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

        await self.audit.log(
            action="user.login",
            entity_type="user",
            actor_id=user.id,
            entity_id=user.id,
            ip_address=ip_address,
            new_value={"role": user.role, "email": user.email},
        )

        logger.info("auth.login_success", user_id=str(user.id), role=user.role)
        return access_token, refresh_token, user

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, User]:
        """Validate refresh token and issue new access token."""
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = uuid.UUID(payload["sub"])

        stmt = (
            select(User)
            .where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
            .options(selectinload(User.team))
        )
        result = await self.db.execute(stmt)
        user: Optional[User] = result.scalar_one_or_none()

        if not user:
            raise UnauthorizedError("User not found or inactive.")

        access_token = create_access_token(user.id, user.role)
        return access_token, user

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
            .options(selectinload(User.team))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Standard authenticated password change."""
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect.")
        is_strong, err_msg = validate_password_strength(new_password)
        if not is_strong:
            raise ValidationError(err_msg)

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        self.db.add(user)
        await self.db.flush()

        await self.audit.log(
            action="user.password_changed",
            entity_type="user",
            actor_id=user.id,
            entity_id=user.id,
        )
        logger.info("auth.password_changed", user_id=str(user.id))

    async def activate_password(
        self, user: User, new_password: str, current_password: Optional[str] = None
    ) -> tuple[User, str, str]:
        """First-login or forced password change activation."""
        if current_password and not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect.")

        if self._is_bootstrap_password(new_password):
            raise ValidationError("New password cannot be the temporary bootstrap password.")

        if verify_password(new_password, user.password_hash):
            raise ValidationError("New password cannot be the same as your current or temporary password.")

        is_strong, err_msg = validate_password_strength(new_password)
        if not is_strong:
            raise ValidationError(err_msg)

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        self.db.add(user)
        await self.db.flush()

        # Mint fresh session tokens
        access_token = create_access_token(user_id=user.id, role=user.role)
        refresh_token = create_refresh_token(user_id=user.id)

        await self.audit.log(
            action="user.password_activated",
            entity_type="user",
            actor_id=user.id,
            entity_id=user.id,
            notes="User completed first-login password activation",
        )
        logger.info("auth.password_activated", user_id=str(user.id))
        return user, access_token, refresh_token

    # ── Email Verification ─────────────────────────────────────────────────────

    async def create_and_send_verification(self, user: User) -> str:
        """Generate a secure expiring verification token and send verification email."""
        raw_token = generate_secure_token()
        now = datetime.now(timezone.utc)
        user.verification_token_hash = hash_token(raw_token)
        user.verification_token_expires_at = now + timedelta(hours=settings.verification_token_expire_hours)
        user.verification_sent_at = now
        self.db.add(user)
        await self.db.flush()

        result = await send_verification_email(
            to_email=user.email,
            recipient_name=user.first_name,
            token=raw_token,
        )
        if not result.ok:
            # Surfaced to the caller as a 503. The surrounding transaction is rolled
            # back, so the undelivered token is not left on the account and the resend
            # cooldown is not started by a send that never happened.
            logger.error(
                "auth.verification_send_failed",
                user_id=str(user.id),
                provider=result.provider,
                error=result.error,
            )
            raise EmailDeliveryError(
                "We could not send the verification email. Please try again shortly."
            )

        logger.info(
            "auth.verification_sent",
            user_id=str(user.id),
            email=user.email,
            provider=result.provider,
            message_id=result.message_id,
        )
        return raw_token

    async def verify_email(self, token: str, email: Optional[str] = None) -> User:
        """
        Verify email with one-time token.
        Token expires after use and cannot be reused.
        """
        if not token or not token.strip():
            raise ValidationError("Verification token is required.")

        target_hash = hash_token(token.strip())
        stmt = select(User).where(
            User.verification_token_hash == target_hash,
            User.deleted_at.is_(None),
        )
        if email:
            stmt = stmt.where(User.normalized_email == normalize_email(email))

        user = (await self.db.execute(stmt)).scalar_one_or_none()
        if not user:
            raise ValidationError("Invalid or expired verification token.")

        now = datetime.now(timezone.utc)
        if user.verification_token_expires_at:
            exp = user.verification_token_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                # Token expired
                user.verification_token_hash = None
                user.verification_token_expires_at = None
                self.db.add(user)
                await self.db.flush()
                raise ValidationError("Verification token has expired. Please request a new one.")

        # Successfully verified — make token one-time unusable
        user.email_verified = True
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        self.db.add(user)
        await self.db.flush()

        await self.audit.log(
            action="user.email_verified",
            entity_type="user",
            actor_id=user.id,
            entity_id=user.id,
            notes="Email address successfully verified",
        )
        logger.info("auth.email_verified", user_id=str(user.id), email=user.email)
        return user

    async def resend_verification(self, email: str) -> None:
        """
        Resend verification email with rate-limiting and cooldown.
        Timing-safe: never reveals whether email is registered.
        """
        normalized = normalize_email(email)
        stmt = select(User).where(User.normalized_email == normalized, User.deleted_at.is_(None))
        user = (await self.db.execute(stmt)).scalar_one_or_none()

        if not user or user.email_verified:
            # Dummy timing balance
            dummy_password_hash()
            logger.info("auth.resend_verification_noop", email=normalized)
            return

        now = datetime.now(timezone.utc)
        if user.verification_sent_at:
            v_sent = user.verification_sent_at
            if v_sent.tzinfo is None:
                v_sent = v_sent.replace(tzinfo=timezone.utc)
            seconds_since = (now - v_sent).total_seconds()
            cooldown = settings.verification_resend_cooldown_seconds
            if seconds_since < cooldown:
                remaining = max(1, int(cooldown - seconds_since))
                raise RateLimitError(
                    f"Please wait {remaining} seconds before requesting another verification email."
                )

        await self.create_and_send_verification(user)
        await self.audit.log(
            action="user.verification_resent",
            entity_type="user",
            actor_id=user.id,
            entity_id=user.id,
        )

    # ── Password Reset Flow ───────────────────────────────────────────────────

    async def request_password_reset(self, email: str) -> None:
        """
        Initiate password reset.
        Timing-safe: does not leak whether email is in system.
        Enforces resend cooldown and invalidates previous token.
        """
        normalized = normalize_email(email)
        stmt = select(User).where(User.normalized_email == normalized, User.deleted_at.is_(None))
        user = (await self.db.execute(stmt)).scalar_one_or_none()

        if not user or not user.is_active:
            dummy_password_hash()
            logger.info("auth.password_reset_noop", email=normalized)
            return

        now = datetime.now(timezone.utc)
        if user.password_reset_sent_at:
            r_sent = user.password_reset_sent_at
            if r_sent.tzinfo is None:
                r_sent = r_sent.replace(tzinfo=timezone.utc)
            seconds_since = (now - r_sent).total_seconds()
            cooldown = 60
            if seconds_since < cooldown:
                remaining = max(1, int(cooldown - seconds_since))
                raise RateLimitError(
                    f"Please wait {remaining} seconds before requesting another reset email."
                )

        raw_token = generate_secure_token()
        user.password_reset_token_hash = hash_token(raw_token)
        user.password_reset_expires_at = now + timedelta(hours=settings.password_reset_token_expire_hours)
        user.password_reset_sent_at = now
        self.db.add(user)
        await self.db.flush()

        result = await send_password_reset_email(
            to_email=user.email,
            recipient_name=user.first_name,
            token=raw_token,
        )
        if not result.ok:
            logger.error(
                "auth.password_reset_send_failed",
                user_id=str(user.id),
                provider=result.provider,
                error=result.error,
            )
            raise EmailDeliveryError(
                "We could not send the password reset email. Please try again shortly."
            )

        await self.audit.log(
            action="user.password_reset_requested",
            entity_type="user",
            actor_id=user.id,
            entity_id=user.id,
        )
        logger.info(
            "auth.password_reset_requested",
            user_id=str(user.id),
            provider=result.provider,
            message_id=result.message_id,
        )

    async def reset_password_with_token(self, token: str, new_password: str) -> User:
        """Reset password using one-time token."""
        if not token or not token.strip():
            raise ValidationError("Reset token is required.")

        if self._is_bootstrap_password(new_password):
            raise ValidationError("New password cannot be the temporary bootstrap password.")

        is_strong, err_msg = validate_password_strength(new_password)
        if not is_strong:
            raise ValidationError(err_msg)

        target_hash = hash_token(token.strip())
        stmt = select(User).where(
            User.password_reset_token_hash == target_hash,
            User.deleted_at.is_(None),
        )
        user = (await self.db.execute(stmt)).scalar_one_or_none()
        if not user:
            raise ValidationError("Invalid or expired password reset token.")

        if verify_password(new_password, user.password_hash):
            raise ValidationError("New password cannot be the same as your current password.")

        now = datetime.now(timezone.utc)
        if user.password_reset_expires_at:
            exp = user.password_reset_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                user.password_reset_token_hash = None
                user.password_reset_expires_at = None
                self.db.add(user)
                await self.db.flush()
                raise ValidationError("Password reset token has expired. Please request a new one.")

        # Update password and clear reset token (one-time usage)
        user.password_hash = hash_password(new_password)
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        user.must_change_password = False
        user.is_locked = False
        user.locked_until = None
        user.login_attempts = 0
        self.db.add(user)
        await self.db.flush()

        await self.audit.log(
            action="user.password_reset_completed",
            entity_type="user",
            actor_id=user.id,
            entity_id=user.id,
            notes="Password successfully reset via token",
        )
        logger.info("auth.password_reset_completed", user_id=str(user.id))
        return user

    @staticmethod
    def _is_bootstrap_password(candidate: str) -> bool:
        """
        True when the candidate equals the configured bootstrap password.

        This used to compare against a hardcoded literal, which stopped matching
        anything once the bootstrap password moved to the BOOTSTRAP_PASSWORD
        environment variable, so the guard silently protected nothing.
        """
        configured = (getattr(settings, "bootstrap_password", "") or "").strip()
        if not configured:
            return False
        return secrets.compare_digest(candidate.strip(), configured)


    # ── Internal lockout helpers ──────────────────────────────────────────────

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
