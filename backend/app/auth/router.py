"""
Auth router — login, logout, refresh, me, change-password, email verification,
activation password set, and password reset.
Rate limited on sensitive auth endpoints.
"""
from datetime import timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    get_current_user,
)
from app.auth.schemas import (
    ActivatePasswordRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LanguageUpdateRequest,
    LoginRequest,
    ResetPasswordRequest,
    ResendVerificationRequest,
    ThemeUpdateRequest,
    TokenResponse,
    UserMeResponse,
    VerifyEmailRequest,
)
from app.auth.service import AuthService
from app.config import get_settings
from app.core.email import get_dev_mailbox
from app.core.ratelimit import limiter
from app.database import get_db
from app.models.user import User

settings = get_settings()
logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

COOKIE_KWARGS = {
    "httponly": True,
    "samesite": "lax",
    "secure": settings.app_env == "production",
    "path": "/",
}


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user. Sets HttpOnly JWT cookies. Returns access token info."""
    ip_address = request.client.host if request.client else "unknown"
    auth_service = AuthService(db)

    access_token, refresh_token, user = await auth_service.login(
        email=body.email,
        password=body.password,
        ip_address=ip_address,
    )

    # Set access token as HttpOnly cookie
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **COOKIE_KWARGS,
    )
    # Set refresh token as HttpOnly cookie (longer lived)
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        **COOKIE_KWARGS,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        must_change_password=getattr(user, "must_change_password", False),
        email_verified=getattr(user, "email_verified", False),
    )


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    """Logout — clear session cookies."""
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")
    logger.info("auth.logout", user_id=str(current_user.id))
    return {"message": "Logged out successfully."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Use refresh token cookie to issue a new access token."""
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_token_value:
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError("No refresh token found.")

    auth_service = AuthService(db)
    access_token, user = await auth_service.refresh_access_token(refresh_token_value)

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **COOKIE_KWARGS,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        must_change_password=getattr(user, "must_change_password", False),
        email_verified=getattr(user, "email_verified", False),
    )


@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the authenticated user's profile."""
    team_name = current_user.team.name if current_user.team else None
    return UserMeResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=current_user.full_name,
        role=current_user.role,
        team_id=str(current_user.team_id) if current_user.team_id else None,
        team_name=team_name,
        is_active=current_user.is_active,
        lead_capacity=current_user.lead_capacity,
        theme_preference=getattr(current_user, "theme_preference", "black_beige") or "black_beige",
        preferred_language=getattr(current_user, "preferred_language", "en") or "en",
        must_change_password=getattr(current_user, "must_change_password", False),
        email_verified=getattr(current_user, "email_verified", False),
    )


@router.patch("/theme")
async def patch_theme(
    body: ThemeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update and persist the user's UI theme preference in the database."""
    current_user.theme_preference = body.theme_preference
    db.add(current_user)
    await db.flush()
    return {"message": "Theme preference updated successfully.", "theme_preference": current_user.theme_preference}


@router.patch("/language")
async def patch_language(
    body: LanguageUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update and persist the user's UI language preference in the database."""
    current_user.preferred_language = body.preferred_language
    db.add(current_user)
    await db.flush()
    return {"message": "Language preference updated successfully.", "preferred_language": current_user.preferred_language}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the authenticated user's password."""
    auth_service = AuthService(db)
    await auth_service.change_password(
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return {"message": "Password changed successfully."}


@router.post("/activate-password")
async def activate_password(
    response: Response,
    body: ActivatePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set personal password upon first activation/login."""
    auth_service = AuthService(db)
    user, access_token, refresh_token = await auth_service.activate_password(
        user=current_user,
        new_password=body.new_password,
        current_password=body.current_password,
    )
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **COOKIE_KWARGS,
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        **COOKIE_KWARGS,
    )
    return {
        "message": "Personal password set successfully.",
        "access_token": access_token,
        "must_change_password": False,
    }


@router.post("/verify-email")
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email address with one-time expiring token."""
    auth_service = AuthService(db)
    user = await auth_service.verify_email(token=body.token, email=body.email)
    return {
        "message": "Email address verified successfully.",
        "email_verified": True,
        "email": user.email,
    }


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resend email verification token (rate limited with cooldown)."""
    auth_service = AuthService(db)
    await auth_service.resend_verification(email=body.email)
    return {
        "message": "If an unverified account exists for this address, a verification link has been sent.",
    }


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Initiate password reset via expiring email token."""
    auth_service = AuthService(db)
    await auth_service.request_password_reset(email=body.email)
    return {
        "message": "If an account matches this email, instructions to reset your password have been sent.",
    }


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    response: Response,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using one-time token. Invalidates prior sessions."""
    auth_service = AuthService(db)
    user = await auth_service.reset_password_with_token(
        token=body.token,
        new_password=body.new_password,
    )
    # Clear any old cookies to force re-login
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")
    return {"message": "Password reset successfully. Please log in with your new password."}


@router.get("/dev-mail")
async def dev_mail(email: Optional[str] = None):
    """Development-only endpoint to inspect generated mock verification and reset tokens."""
    if settings.app_env not in ("development", "test") and not settings.app_debug:
        return {"error": "Not available in production"}
    msgs = get_dev_mailbox()
    if email:
        target = email.strip().lower()
        msgs = [m for m in msgs if str(m.get("to", "")).strip().lower() == target]
    return {"messages": msgs}


@router.post("/debug-login")
async def debug_login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    TEMPORARY DIAGNOSTIC ENDPOINT — returns the raw exception if login fails.
    Remove after production issue is resolved.
    """
    import traceback as tb_mod
    try:
        auth_service = AuthService(db)
        access_token, refresh_token, user = await auth_service.login(
            email=body.email,
            password=body.password,
            ip_address="debug",
        )
        return {"status": "ok", "user_id": str(user.id), "role": user.role}
    except Exception as exc:
        full_tb = tb_mod.format_exc()
        return {
            "status": "error",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": full_tb,
        }
