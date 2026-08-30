"""
Unit tests for security, hashing, tokens, and normalizations.
"""
import uuid
import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    normalize_email,
    normalize_phone,
)
from app.core.exceptions import UnauthorizedError


def test_password_hashing():
    pwd = "SecurePassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_token():
    user_id = uuid.uuid4()
    role = "ADMIN"
    token = create_access_token(user_id, role)
    assert token is not None

    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == str(user_id)
    assert payload["role"] == role
    assert payload["type"] == "access"


def test_jwt_type_mismatch():
    user_id = uuid.uuid4()
    refresh_token = create_refresh_token(user_id)

    with pytest.raises(UnauthorizedError):
        decode_token(refresh_token, expected_type="access")


def test_email_normalization():
    assert normalize_email("  SALEH@AlphaPro.COM  ") == "saleh@alphapro.com"
    assert normalize_email("Test.User@Domain.Co.UK") == "test.user@domain.co.uk"


def test_phone_normalization():
    assert normalize_phone("+966 (50) 112-2334") == "966501122334"
    assert normalize_phone("055 223 3445") == "0552233445"
