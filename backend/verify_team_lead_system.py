"""
Comprehensive Verification Suite for the 3-Role Operational Architecture:
TEAM LEAD (Qusai) -> MANAGER (Nour) -> USER (Saleh)
"""
import asyncio
import uuid
import structlog
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import create_app
from app.database import AsyncSessionLocal
from app.migrations import run_role_migrations
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)


async def run_verification():
    print("=" * 70)
    print("ALPHA PRO MENA CRM — TEAM LEAD & 3-ROLE ARCHITECTURE VERIFICATION")
    print("=" * 70)

    # 1. Run Role Migrations
    print("\n[Step 1] Running automatic role migrations and Qusai Team Lead seeding...")
    await run_role_migrations()

    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User).where(User.deleted_at.is_(None)))).scalars().all()
        print(f"[OK] Total active accounts: {len(users)}")
        for u in users:
            print(f"   - {u.full_name} ({u.email}): Role = '{u.role}'")
            if u.role not in [UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.USER, "TEAM_LEAD", "MANAGER", "USER"]:
                print(f"[ERROR] User {u.email} has non-standard role: {u.role}")
                return False

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as client:
        # 2. Team Lead Authentication (Qusai)
        print("\n[Step 2] Authenticating as Primary Team Lead (qusai@alphapro.com)...")
        login_res = await client.post("/auth/login", json={"email": "qusai@alphapro.com", "password": "TeamLead123!"})
        if login_res.status_code != 200:
            print(f"[FAIL] Team Lead login failed: {login_res.status_code} {login_res.text}")
            return False
        
        team_lead_token = login_res.json()["access_token"]
        team_lead_headers = {"Authorization": f"Bearer {team_lead_token}"}
        print("[OK] Authenticated successfully as Team Lead (Qusai)")

        # Verify /auth/me for Team Lead
        me_res = await client.get("/auth/me", headers=team_lead_headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        print(f"[OK] Auth Me confirmed: Name = {me_data['full_name']}, Role = {me_data['role']}")
        assert me_data["role"] in ("TEAM_LEAD", UserRole.TEAM_LEAD)

        # 3. Team Lead Dashboard & Manager Performance Oversight
        print("\n[Step 3] Testing Team Lead Dashboard & Manager Performance Overview...")
        dash_res = await client.get("/reports/dashboard", headers=team_lead_headers)
        assert dash_res.status_code == 200, f"Dashboard failed: {dash_res.text}"
        dash_data = dash_res.json()["data"]

        kpis = dash_data["kpis"]
        print(f"[OK] Total CRM Metrics:")
        print(f"   - Total Calls: {kpis['total_calls']}")
        print(f"   - Active Contacts: {kpis.get('active_leads', 0)}")
        print(f"   - Unassigned Leads Pool: {kpis.get('unassigned_leads', 0)}")
        print(f"   - Overdue Tasks: {kpis['overdue_tasks']}")

        mgr_perf = dash_data.get("manager_performance", [])
        print(f"[OK] Manager & Team Performance Table ({len(mgr_perf)} teams evaluated):")
        for m in mgr_perf:
            print(f"   - Team: {m['team_name']} | Manager: {m['manager_name']} | Active Reps: {m['members_count']} | Calls: {m['calls']} | Score: {m['team_performance_score']}/100")

        # 4. System Settings Management (Team Lead Only)
        print("\n[Step 4] Testing Team Lead System Settings (GET & PATCH)...")
        settings_get = await client.get("/admin/settings", headers=team_lead_headers)
        assert settings_get.status_code == 200
        print(f"[OK] System settings retrieved: No-Answer Retry = {settings_get.json()['data']['no_answer_retry_hours']}h")

        settings_patch = await client.patch("/admin/settings", json={"no_answer_retry_hours": 48, "email_followup_delay_hours": 24}, headers=team_lead_headers)
        assert settings_patch.status_code == 200
        print(f"[OK] System settings updated by Team Lead: {settings_patch.json()['data']['no_answer_retry_hours']}h retry cadence")

        # 5. User Management by Team Lead
        print("\n[Step 5] Testing User Management by Team Lead (Create, Update, Disable, Reactivate)...")
        test_email = f"sales_rep_{uuid.uuid4().hex[:6]}@alphapro.com"
        create_user_res = await client.post("/users", json={
            "email": test_email,
            "first_name": "Tariq",
            "last_name": "TestRep",
            "password": "Password123!",
            "role": "USER",
            "lead_capacity": 450,
        }, headers=team_lead_headers)
        assert create_user_res.status_code == 201, f"Failed creating user: {create_user_res.text}"
        new_user_id = create_user_res.json()["id"]
        print(f"[OK] New Sales User created: {test_email} (ID: {new_user_id})")

        # Disable user
        disable_res = await client.post(f"/users/{new_user_id}/disable", headers=team_lead_headers)
        assert disable_res.status_code == 200
        assert disable_res.json()["is_active"] is False
        print(f"[OK] User disabled successfully")

        # Reactivate user
        reactivate_res = await client.post(f"/users/{new_user_id}/reactivate", headers=team_lead_headers)
        assert reactivate_res.status_code == 200
        assert reactivate_res.json()["is_active"] is True
        print(f"[OK] User reactivated successfully")

        # 6. Manager Role & Privilege Escalation Tests
        print("\n[Step 6] Testing Manager Permissions & Privilege Boundary Enforcement...")
        mgr_login = await client.post("/auth/login", json={"email": "manager@alphapro.com", "password": "Manager123!"})
        assert mgr_login.status_code == 200
        mgr_token = mgr_login.json()["access_token"]
        mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
        print("[OK] Authenticated as Manager (Nour Haddad)")

        # Manager CAN access operational dashboard
        mgr_dash = await client.get("/reports/dashboard", headers=mgr_headers)
        assert mgr_dash.status_code == 200
        print("[OK] Manager permitted to access operational dashboard")

        # Manager CANNOT modify system settings (403 Forbidden)
        mgr_patch_settings = await client.patch("/admin/settings", json={"no_answer_retry_hours": 12}, headers=mgr_headers)
        print(f"   - Manager -> PATCH /admin/settings: Status {mgr_patch_settings.status_code} (Expected 403)")
        assert mgr_patch_settings.status_code == 403, f"Privilege escalation! Status: {mgr_patch_settings.status_code}"

        # Manager CANNOT create users (403 Forbidden)
        mgr_create_user = await client.post("/users", json={
            "email": "hacked@alphapro.com", "first_name": "Hack", "last_name": "User", "password": "Password123!", "role": "TEAM_LEAD"
        }, headers=mgr_headers)
        print(f"   - Manager -> POST /users: Status {mgr_create_user.status_code} (Expected 403)")
        assert mgr_create_user.status_code == 403, f"Privilege escalation! Status: {mgr_create_user.status_code}"

        # 7. Sales User Role & Strict Privilege Isolation Tests
        print("\n[Step 7] Testing Sales User Permissions & Strict Isolation...")
        user_login = await client.post("/auth/login", json={"email": "saleh@alphapro.com", "password": "Sales123!"})
        assert user_login.status_code == 200
        user_token = user_login.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}
        print("[OK] Authenticated as Sales User (Saleh Al-Ghamdi)")

        # Sales User CANNOT access audit logs (403 Forbidden)
        user_audit = await client.get("/audit-logs", headers=user_headers)
        print(f"   - Sales User -> GET /audit-logs: Status {user_audit.status_code} (Expected 403)")
        assert user_audit.status_code == 403, f"Privilege escalation! Status: {user_audit.status_code}"

        # Sales User CANNOT access system settings (403 Forbidden)
        user_settings = await client.get("/admin/settings", headers=user_headers)
        print(f"   - Sales User -> GET /admin/settings: Status {user_settings.status_code} (Expected 403)")
        assert user_settings.status_code == 403, f"Privilege escalation! Status: {user_settings.status_code}"

        # Sales User CANNOT distribute leads (403 Forbidden)
        user_dist = await client.post("/admin/leads/distribute", json={"strategy": "ROUND_ROBIN"}, headers=user_headers)
        print(f"   - Sales User -> POST /admin/leads/distribute: Status {user_dist.status_code} (Expected 403)")
        assert user_dist.status_code == 403, f"Privilege escalation! Status: {user_dist.status_code}"

        print("\n" + "=" * 70)
        print("ALL 3-ROLE & TEAM LEAD VERIFICATION TESTS PASSED (100% SUCCESS)!")
        print("=" * 70)
        return True


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    if not success:
        exit(1)
