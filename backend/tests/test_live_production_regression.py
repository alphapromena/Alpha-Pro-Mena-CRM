"""
test_live_production_regression.py
Asserts all endpoints reported as failing in production:
1. GET /api/v1/tasks?per_page=100 -> 200
2. GET /api/v1/tasks?per_page=8&status=OPEN -> 200
3. POST /api/v1/tasks -> 201
4. Task priority and overdue filters -> 200
5. GET /api/v1/reports/dashboard?... -> 200
6. GET /api/v1/users -> 403 for regular USER, 200 for MANAGER/TEAM_LEAD
7. POST /api/v1/admin/run-migrations -> 200 for MANAGER/TEAM_LEAD
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, normalize_email
from app.models.user import User, UserRole
from app.models.contact import Contact


async def _create_user(db: AsyncSession, role: UserRole, prefix: str) -> tuple[User, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@alphapromena.com"
    user = User(
        email=email,
        normalized_email=normalize_email(email),
        first_name=prefix.capitalize(),
        last_name="Tester",
        password_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(user_id=user.id, role=user.role)
    return user, token


@pytest.mark.asyncio
async def test_tasks_list_endpoints_succeed(client: AsyncClient, db_session: AsyncSession):
    user, token = await _create_user(db_session, UserRole.USER, "sales_tasks")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET /api/v1/tasks?per_page=100 -> 200
    res100 = await client.get("/api/v1/tasks?per_page=100", headers=headers)
    assert res100.status_code == 200, f"per_page=100 failed: {res100.text}"
    assert "data" in res100.json()

    # 2. GET /api/v1/tasks?per_page=8&status=OPEN -> 200
    res_open = await client.get("/api/v1/tasks?per_page=8&status=OPEN", headers=headers)
    assert res_open.status_code == 200, f"status=OPEN failed: {res_open.text}"

    # 3. Priority and overdue filters -> 200
    res_filt = await client.get("/api/v1/tasks?priority=HIGH&is_overdue=true", headers=headers)
    assert res_filt.status_code == 200, f"priority/overdue filters failed: {res_filt.text}"


@pytest.mark.asyncio
async def test_task_creation_succeeds(client: AsyncClient, db_session: AsyncSession):
    user, token = await _create_user(db_session, UserRole.USER, "sales_create")
    headers = {"Authorization": f"Bearer {token}"}

    task_payload = {
        "title": "Production Test Task",
        "description": "Validating task creation",
        "priority": "HIGH",
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    res = await client.post("/api/v1/tasks", json=task_payload, headers=headers)
    assert res.status_code == 201, f"Task creation failed: {res.text}"
    created = res.json()["data"]
    assert created["title"] == "Production Test Task"
    assert created["assigned_to"] == str(user.id)


@pytest.mark.asyncio
async def test_dashboard_report_succeeds(client: AsyncClient, db_session: AsyncSession):
    user, token = await _create_user(db_session, UserRole.USER, "sales_dash")
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/v1/reports/dashboard?range=today", headers=headers)
    assert res.status_code == 200, f"Dashboard failed: {res.text}"
    data = res.json()["data"]
    assert "calls_breakdown" in data or "conversion_rates" in data or "user_performance" in data


@pytest.mark.asyncio
async def test_users_endpoint_rbac_enforcement(client: AsyncClient, db_session: AsyncSession):
    # Regular user gets 403
    sales_user, sales_token = await _create_user(db_session, UserRole.USER, "reg_sales")
    res_sales = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {sales_token}"})
    assert res_sales.status_code == 403, f"Regular user should receive 403 on /users: {res_sales.status_code}"

    # Manager gets 200
    mgr_user, mgr_token = await _create_user(db_session, UserRole.MANAGER, "mgr_user")
    res_mgr = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {mgr_token}"})
    assert res_mgr.status_code == 200, f"Manager should receive 200 on /users: {res_mgr.status_code}"

    # Team Lead gets 200
    lead_user, lead_token = await _create_user(db_session, UserRole.TEAM_LEAD, "lead_user")
    res_lead = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {lead_token}"})
    assert res_lead.status_code == 200, f"Team Lead should receive 200 on /users: {res_lead.status_code}"


@pytest.mark.asyncio
async def test_run_migrations_endpoint(client: AsyncClient, db_session: AsyncSession):
    # Regular user cannot trigger migrations
    _, sales_token = await _create_user(db_session, UserRole.USER, "mig_sales")
    res_sales = await client.post("/api/v1/admin/run-migrations", headers={"Authorization": f"Bearer {sales_token}"})
    assert res_sales.status_code == 403

    # Manager can trigger migrations
    _, mgr_token = await _create_user(db_session, UserRole.MANAGER, "mig_mgr")
    res_mgr = await client.post("/api/v1/admin/run-migrations", headers={"Authorization": f"Bearer {mgr_token}"})
    assert res_mgr.status_code == 200
    assert res_mgr.json()["data"]["success"] is True
