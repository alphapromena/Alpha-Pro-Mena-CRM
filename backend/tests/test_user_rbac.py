"""
test_user_rbac.py — Integration tests asserting the corrected RBAC policy
for user management:
  - TEAM_LEAD  can  create/edit/disable users
  - MANAGER    can  create/edit/disable users (was broken, now fixed)
  - USER       cannot create/edit/disable users (must still get 403)
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, normalize_email
from app.models.user import User, UserRole


async def _create_user(db: AsyncSession, role: UserRole, email_prefix: str) -> tuple[User, str]:
    email = f"{email_prefix}_{uuid.uuid4().hex[:6]}@alphapromena.com"
    user = User(
        email=email,
        normalized_email=normalize_email(email),
        first_name=email_prefix.capitalize(),
        last_name="Test",
        password_hash=hash_password("Pass123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(user_id=user.id, role=user.role)
    return user, token


def _new_user_payload(suffix: str = "rbactest") -> dict:
    return {
        "email": f"rbac_{suffix}_{uuid.uuid4().hex[:6]}@test.example.com",
        "first_name": "RBAC",
        "last_name": "Test",
        "password": "TestPass123!",
        "role": "USER",
    }


# ── Tests: POST /api/v1/users ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_team_lead_can_create_user(client: AsyncClient, db_session: AsyncSession):
    """TEAM_LEAD must receive 201 Created — not 403."""
    _, token = await _create_user(db_session, UserRole.TEAM_LEAD, "lead")
    resp = await client.post(
        "/api/v1/users",
        json=_new_user_payload("teamlead"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"TEAM_LEAD should get 201 on POST /api/v1/users. Got: {resp.status_code} {resp.text}"


@pytest.mark.asyncio
async def test_manager_can_create_user(client: AsyncClient, db_session: AsyncSession):
    """MANAGER must receive 201 Created — NOT 403."""
    _, token = await _create_user(db_session, UserRole.MANAGER, "mgr")
    resp = await client.post(
        "/api/v1/users",
        json=_new_user_payload("manager"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, (
        f"MANAGER should get 201 on POST /api/v1/users. Got: {resp.status_code} {resp.text}\n"
        "Manager RBAC fix may not have applied correctly."
    )


@pytest.mark.asyncio
async def test_sales_user_cannot_create_user(client: AsyncClient, db_session: AsyncSession):
    """Sales USER must receive 403 on POST /api/v1/users."""
    _, token = await _create_user(db_session, UserRole.USER, "sales")
    resp = await client.post(
        "/api/v1/users",
        json=_new_user_payload("salesuser"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, (
        f"Sales USER should get 403 on POST /api/v1/users. Got: {resp.status_code} {resp.text}"
    )


# ── Tests: PATCH /api/v1/users/{id} ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_manager_can_call_patch_users(client: AsyncClient, db_session: AsyncSession):
    """MANAGER calling PATCH /api/v1/users/{id} must succeed (200 OK)."""
    target_user, _ = await _create_user(db_session, UserRole.USER, "target")
    _, token = await _create_user(db_session, UserRole.MANAGER, "mgr")
    resp = await client.patch(
        f"/api/v1/users/{target_user.id}",
        json={"first_name": "UpdatedByMgr"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, (
        f"MANAGER should get 200 on PATCH /api/v1/users. Got: {resp.status_code} {resp.text}"
    )


@pytest.mark.asyncio
async def test_sales_user_cannot_patch_users(client: AsyncClient, db_session: AsyncSession):
    """Sales USER must get 403 on PATCH /api/v1/users/{id}."""
    target_user, _ = await _create_user(db_session, UserRole.USER, "target")
    _, token = await _create_user(db_session, UserRole.USER, "sales")
    resp = await client.patch(
        f"/api/v1/users/{target_user.id}",
        json={"first_name": "Hacked"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, (
        f"Sales USER should get 403 on PATCH /api/v1/users. Got: {resp.status_code}"
    )


# ── Tests: Disable / Reactivate ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manager_can_call_disable(client: AsyncClient, db_session: AsyncSession):
    """MANAGER must be allowed to disable a user."""
    target_user, _ = await _create_user(db_session, UserRole.USER, "target")
    _, token = await _create_user(db_session, UserRole.MANAGER, "mgr")
    resp = await client.post(
        f"/api/v1/users/{target_user.id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, (
        f"MANAGER should get 200 on /disable. Got: {resp.status_code} {resp.text}"
    )


@pytest.mark.asyncio
async def test_sales_user_cannot_disable(client: AsyncClient, db_session: AsyncSession):
    """Sales USER must get 403 on /disable."""
    target_user, _ = await _create_user(db_session, UserRole.USER, "target")
    _, token = await _create_user(db_session, UserRole.USER, "sales")
    resp = await client.post(
        f"/api/v1/users/{target_user.id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, (
        f"Sales USER should get 403 on /disable. Got: {resp.status_code}"
    )
