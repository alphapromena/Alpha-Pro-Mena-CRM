"""
Integration tests for Authentication API and RBAC boundaries.
"""
import pytest
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_login_success(client, seed_test_users):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert resp.cookies.get("access_token") is not None


@pytest.mark.asyncio
async def test_login_invalid_password(client, seed_test_users):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_sales_user_cannot_access_admin_users(client, seed_test_users):
    sales_user = seed_test_users["sales"]
    token = create_access_token(sales_user.id, sales_user.role)

    resp = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_access_admin_users(client, seed_test_users):
    admin_user = seed_test_users["admin"]
    token = create_access_token(admin_user.id, admin_user.role)

    resp = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "data" in resp.json()
