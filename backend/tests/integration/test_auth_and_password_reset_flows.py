"""
Integration tests for first-login bootstrap password, forced password change,
server-side route guard, forgot password flow, and email verification.
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_password, normalize_email, generate_secure_token, hash_token
from app.models.user import User, UserRole, Team
from app.models.contact import Contact, ContactStatus
from app.models.company import Company
from app.models.audit import AuditLog

BOOTSTRAP_EMAILS = [
    ("saleh@alphapromena.com", "Saleh", UserRole.USER),
    ("hassan@alphapromena.com", "Hassan", UserRole.USER),
    ("amin@alphapromena.com", "Amin", UserRole.USER),
    ("ghaida@alphapromena.com", "Ghaida", UserRole.USER),
    ("qusai@alphapromena.com", "Qusai", UserRole.TEAM_LEAD),
    ("aseel@alphapromena.com", "Aseel", UserRole.DATA_OPS),
    ("abdallah@alphapromena.com", "Abdallah", UserRole.MANAGER),
]


async def _seed_seven_team_members(db: AsyncSession, temporary_password: str = "123456789") -> list[User]:
    """Helper to seed all 7 team users with the temporary bootstrap password."""
    team = Team(name="MENA Enterprise Sales", description="Main team")
    db.add(team)
    await db.flush()

    users = []
    hashed = hash_password(temporary_password)
    for email, first_name, role in BOOTSTRAP_EMAILS:
        u = User(
            email=email,
            normalized_email=normalize_email(email),
            first_name=first_name,
            last_name="",
            password_hash=hashed,
            role=role,
            team_id=team.id,
            is_active=True,
            is_locked=False,
            login_attempts=0,
            must_change_password=True,
            email_verified=True,
        )
        db.add(u)
        users.append(u)
    await db.flush()
    return users


# ─────────────────────────────────────────────────────────────────────────────
# 1. BOOTSTRAP PASSWORD & FORCED FIRST-LOGIN CHANGE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_seven_team_users_authenticate_with_bootstrap_password(
    client: AsyncClient, db_session: AsyncSession
):
    """All seven users authenticate with temporary password 123456789 and must_change_password=True."""
    await _seed_seven_team_members(db_session, "123456789")

    for email, _, _ in BOOTSTRAP_EMAILS:
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "123456789"})
        assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
        data = resp.json()
        assert data["must_change_password"] is True
        assert "access_token" in data
        assert "123456789" not in resp.text
        assert "password_hash" not in resp.text
        assert "password" not in data


@pytest.mark.asyncio
async def test_must_change_password_blocks_protected_routes(
    client: AsyncClient, db_session: AsyncSession
):
    """Server-side guard strictly returns 403 Forbidden for any CRM data access while must_change_password is True."""
    await _seed_seven_team_members(db_session, "123456789")

    # Log in as saleh
    login_res = await client.post("/api/v1/auth/login", json={"email": "saleh@alphapromena.com", "password": "123456789"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me is allowed so the frontend knows to redirect
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["must_change_password"] is True

    # Protected CRM endpoints MUST return 403 Forbidden
    contacts_res = await client.get("/api/v1/contacts", headers=headers)
    assert contacts_res.status_code == 403
    assert "Password change is required" in contacts_res.json()["error"]["message"]

    demos_res = await client.get("/api/v1/demos", headers=headers)
    assert demos_res.status_code == 403

    tasks_res = await client.get("/api/v1/tasks", headers=headers)
    assert tasks_res.status_code == 403

    reports_res = await client.get("/api/v1/reports/dashboard", headers=headers)
    assert reports_res.status_code == 403


@pytest.mark.asyncio
async def test_password_activation_validations_and_lifecycle(
    client: AsyncClient, db_session: AsyncSession
):
    """Test activation rejects bootstrap password and weak passwords, then accepts strong personal password."""
    await _seed_seven_team_members(db_session, "123456789")

    login_res = await client.post("/api/v1/auth/login", json={"email": "saleh@alphapromena.com", "password": "123456789"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cannot reuse bootstrap password 123456789
    reused_res = await client.post(
        "/api/v1/auth/activate-password",
        headers=headers,
        json={"current_password": "123456789", "new_password": "123456789"},
    )
    assert reused_res.status_code == 422

    # 2. Cannot use weak password
    weak_res = await client.post(
        "/api/v1/auth/activate-password",
        headers=headers,
        json={"current_password": "123456789", "new_password": "weak"},
    )
    assert weak_res.status_code == 422

    # 3. Successful activation with strong personal password
    good_res = await client.post(
        "/api/v1/auth/activate-password",
        headers=headers,
        json={"current_password": "123456789", "new_password": "SalehPersonalPass2026!"},
    )
    assert good_res.status_code == 200
    good_data = good_res.json()
    assert good_data["must_change_password"] is False
    new_token = good_data["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 4. Protected routes are now accessible
    contacts_res = await client.get("/api/v1/contacts", headers=new_headers)
    assert contacts_res.status_code == 200

    # 5. Old temporary password 123456789 no longer works
    old_login = await client.post("/api/v1/auth/login", json={"email": "saleh@alphapromena.com", "password": "123456789"})
    assert old_login.status_code == 401

    # 6. New personal password logs in successfully
    new_login = await client.post("/api/v1/auth/login", json={"email": "saleh@alphapromena.com", "password": "SalehPersonalPass2026!"})
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. FORGOT PASSWORD & RESET FLOW
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_works_for_all_team_users(
    client: AsyncClient, db_session: AsyncSession
):
    """Forgot password initiates successfully for saleh and all approved team members."""
    await _seed_seven_team_members(db_session, "123456789")

    # 1. Works for saleh
    res_saleh = await client.post("/api/v1/auth/forgot-password", json={"email": "saleh@alphapromena.com"})
    assert res_saleh.status_code == 200
    assert "instructions to reset your password" in res_saleh.json()["message"]

    # 2. Works for unknown email (anti-enumeration returns generic 200)
    res_unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@alphapromena.com"})
    assert res_unknown.status_code == 200
    assert "instructions to reset your password" in res_unknown.json()["message"]


@pytest.mark.asyncio
async def test_forgot_password_resend_cooldown(
    client: AsyncClient, db_session: AsyncSession
):
    """
    A second forgot-password request inside the cooldown is suppressed silently.

    It must answer exactly like the first one. Returning 429 here used to confirm
    that the address was registered, because an unknown address always got 200.
    The suppression is asserted through the mailbox: no second email is sent.
    """
    await _seed_seven_team_members(db_session, "123456789")
    target = "hassan@alphapromena.com"

    res1 = await client.post("/api/v1/auth/forgot-password", json={"email": target})
    assert res1.status_code == 200

    after_first = await client.get(f"/api/v1/auth/dev-mail?email={target}")
    sent_after_first = len(after_first.json()["messages"])
    assert sent_after_first == 1

    res2 = await client.post("/api/v1/auth/forgot-password", json={"email": target})
    assert res2.status_code == 200
    assert res2.json()["message"] == res1.json()["message"]

    # The cooldown held: still exactly one email.
    after_second = await client.get(f"/api/v1/auth/dev-mail?email={target}")
    assert len(after_second.json()["messages"]) == sent_after_first

    # And an address that does not exist is indistinguishable from the one that does.
    unknown = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@alphapromena.com"}
    )
    assert unknown.status_code == res2.status_code
    assert unknown.json()["message"] == res2.json()["message"]


@pytest.mark.asyncio
async def test_password_reset_with_token_execution(
    client: AsyncClient, db_session: AsyncSession
):
    """Reset password with token updates credentials and invalidates previous token."""
    await _seed_seven_team_members(db_session, "123456789")

    # 1. Request reset for amin
    req_res = await client.post("/api/v1/auth/forgot-password", json={"email": "amin@alphapromena.com"})
    assert req_res.status_code == 200

    # Retrieve mock mail token
    mail_res = await client.get("/api/v1/auth/dev-mail?email=amin@alphapromena.com")
    assert mail_res.status_code == 200
    msgs = mail_res.json()["messages"]
    assert len(msgs) > 0
    token = msgs[0]["token"]

    # 2. Reset rejects temporary bootstrap password
    rej_res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "123456789"},
    )
    assert rej_res.status_code == 422

    # 3. Reset succeeds with strong new password
    ok_res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AminResetPass2026!"},
    )
    assert ok_res.status_code == 200

    # 4. Token cannot be reused
    reuse_res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass2026!"},
    )
    assert reuse_res.status_code == 400

    # 5. Old password no longer works
    old_login = await client.post("/api/v1/auth/login", json={"email": "amin@alphapromena.com", "password": "123456789"})
    assert old_login.status_code == 401

    # 6. New password works
    new_login = await client.post("/api/v1/auth/login", json={"email": "amin@alphapromena.com", "password": "AminResetPass2026!"})
    assert new_login.status_code == 200
