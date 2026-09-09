"""
Security utilities — password hashing (bcrypt) and JWT token management.
Never expose these internals beyond this module.
"""
import secrets
import uuid
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
import bcrypt

from app.config import get_settings
from app.core.exceptions import UnauthorizedError

settings = get_settings()

# Token type constants
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt with work factor 12."""
    pwd_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    """
    A genuine bcrypt hash of a random secret. Verified against when a login targets an
    unknown email so the request costs the same time as a real password check
    (prevents user enumeration through response timing).
    """
    return hash_password(secrets.token_urlsafe(32))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """Create a short-lived JWT access token (15 minutes)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a long-lived JWT refresh token (7 days), stored in HttpOnly cookie."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": REFRESH_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str) -> dict:
    """Decode and validate a JWT token. Raises UnauthorizedError on failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != expected_type:
            raise UnauthorizedError("Invalid token type.")
        return payload
    except JWTError:
        raise UnauthorizedError("Invalid or expired token.")


def normalize_email(email: str) -> str:
    """Lowercase and strip whitespace from an email address."""
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    """Strip all non-numeric characters from a phone number."""
    if not phone:
        return ""
    return "".join(c for c in phone if c.isdigit())


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Enforces production password policy:
    - Minimum 8 characters
    - At least one lowercase letter
    - At least one uppercase letter
    - At least one digit or special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.isdigit() or not c.isalnum() for c in password):
        return False, "Password must contain at least one digit or special character."
    return True, ""


import hashlib


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of a verification or reset token for secure DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_hash(token: str, expected_hash: Optional[str]) -> bool:
    """Timing-safe verification of token against its stored SHA-256 hash."""
    if not token or not expected_hash:
        return False
    candidate_hash = hash_token(token)
    return secrets.compare_digest(candidate_hash, expected_hash)


def generate_secure_token() -> str:
    """Generate a high-entropy URL-safe token (32 bytes / 43 chars)."""
    return secrets.token_urlsafe(32)


def validate_company_email(email: str, allowed_domain: Optional[str] = None) -> tuple[bool, str]:
    """
    Validates company email:
    - Must contain valid local-part and domain with top-level domain (TLD)
    - Domain must match configured COMPANY_EMAIL_DOMAIN
    - Reject invalid domains without TLD like '@alphapromena'
    """
    normalized = normalize_email(email)
    if "@" not in normalized:
        return False, "Invalid email address format."
    local_part, _, domain = normalized.partition("@")
    if not local_part or not domain:
        return False, "Email must have both username and domain."
    if "." not in domain or domain.endswith("."):
        return False, f"Domain '@{domain}' is not a valid fully-qualified domain with a top-level domain."

    target_domain = (allowed_domain or settings.company_email_domain or "alphapromena.com").strip().lower()
    if domain != target_domain:
        return False, f"Account creation is restricted to approved company domain '@{target_domain}'."
    return True, ""
