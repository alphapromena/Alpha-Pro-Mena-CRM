"""
Users schemas.
"""
import re
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class UserCreateRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: str
    role: str = "USER"
    team_id: Optional[str] = None
    lead_capacity: int = 500

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        valid = ["USER", "MANAGER", "TEAM_LEAD", "ADMIN", "TEAM_LEADER", "SALES_USER"]
        if v not in valid:
            raise ValueError(f"Role must be one of: USER, MANAGER, TEAM_LEAD")
        # Normalize legacy roles
        if v in ("ADMIN", "TEAM_LEADER"):
            return "TEAM_LEAD"
        if v == "SALES_USER":
            return "USER"
        return v


class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    team_id: Optional[str] = None
    is_active: Optional[bool] = None
    lead_capacity: Optional[int] = None


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: str
    team_id: Optional[str]
    team_name: Optional[str]
    is_active: bool
    is_locked: bool
    lead_capacity: int
    last_login_at: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    data: list[UserResponse]
    meta: dict
