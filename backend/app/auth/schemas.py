"""
Auth schemas — request/response Pydantic models.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
import re


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Password is required.")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    must_change_password: bool = False
    email_verified: bool = False
    # True when this request actually dispatched a verification email, so the UI can
    # say "we just sent a code to <address>" instead of asking for one out of nowhere.
    verification_sent: bool = False


class UserMeResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: str
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    is_active: bool
    lead_capacity: int
    theme_preference: str = "black_beige"
    preferred_language: str = "en"
    must_change_password: bool = False
    email_verified: bool = False

    model_config = {"from_attributes": True}


class ThemeUpdateRequest(BaseModel):
    theme_preference: str


class LanguageUpdateRequest(BaseModel):
    preferred_language: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not (re.search(r"[0-9]", v) or re.search(r"[^a-zA-Z0-9]", v)):
            raise ValueError("Password must contain at least one digit or symbol.")
        return v


class ActivatePasswordRequest(BaseModel):
    """Used when user must set a personal password upon first activation / rollout."""
    new_password: str
    current_password: Optional[str] = None

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.strip() == "123456789":
            raise ValueError("New password cannot be the temporary bootstrap password.")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not (re.search(r"[0-9]", v) or re.search(r"[^a-zA-Z0-9]", v)):
            raise ValueError("Password must contain at least one digit or symbol.")
        return v


class VerifyEmailRequest(BaseModel):
    token: str
    email: Optional[EmailStr] = None


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.strip() == "123456789":
            raise ValueError("New password cannot be the temporary bootstrap password.")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not (re.search(r"[0-9]", v) or re.search(r"[^a-zA-Z0-9]", v)):
            raise ValueError("Password must contain at least one digit or symbol.")
        return v
