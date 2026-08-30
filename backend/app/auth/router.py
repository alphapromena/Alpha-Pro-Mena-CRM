"""
Auth router — login, logout, refresh, me, change-password.
Rate limited on login endpoint.
"""
from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    get_current_user,
)
from app.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserMeResponse,
)
from app.auth.service import AuthService
from app.config import get_settings
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
    )


from app.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserMeResponse,
    ThemeUpdateRequest,
    LanguageUpdateRequest,
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
