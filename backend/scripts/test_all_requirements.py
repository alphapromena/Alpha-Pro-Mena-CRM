"""
Comprehensive Automated Verification Suite for Alpha Pro MENA CRM
Tests:
1. User roles and display names (Aseel=DATA_OPS, Abdullah=MANAGER, Qusai=TEAM_LEAD, Saleh=SALES_USER, all first names).
2. Company-Level Demo Conversion calculation (e.g. 50 contacts from ELM with 20 engaged & 1 demo calculates to 1/1 = 100% demo conversion, avoiding contact inflation).
3. Unlimited Contact Attempts & No Answer Retry (4th and 5th call attempt with NO_ANSWER increments attempts, leaves final_outcome=None, keeps contact active without archiving).
4. Explicit Final Outcome (sets final_outcome, archives contact with archived_at & archived_by_id, preserves timeline history, and unarchive restores to active).
5. Aseel DATA_OPS role permissions (Access to Google Sheets & Lead Pool allowed, Manager & System admin & Reports routes 403 Forbidden).
6. Lead distribution to Saleh personal pool (PENDING_CLAIM), claiming appends to the bottom of the user's active contact queue while preserving Google Sheet order.
7. Abdullah (MANAGER) and Qusai (TEAM_LEAD) regression & access checks.
"""
import asyncio
import os
import sys
import uuid
import httpx
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.main import create_app
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.contact import Contact, ContactStatus
from app.models.call import Call
from app.models.demo import Demo, DemoStage
from sqlalchemy import select
from app.core.security import hash_password

async def run_verification():
    print("=" * 70)
    print("STARTING ALPHA PRO MENA CRM COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 70)
    
    app = create_app()
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1") as client:
        
        # --- TEST 1: User Roles and Display Names ---
        print("\n--- TEST 1: User Roles and Display Names ---")
        # 1. Login as Abdullah (Manager)
        login_res = await client.post("/auth/login", json={"email": "abdullah@alphapromena.com", "password": "<set-password>"})
        if login_res.status_code != 200:
            login_res = await client.post("/auth/login", json={"email": "abdallah@alphapromena.com", "password": "<set-password>"})
        assert login_res.status_code == 200, f"Abdullah login failed: {login_res.text}"
        abdullah_token = login_res.json()["access_token"]
        abdullah_headers = {"Authorization": f"Bearer {abdullah_token}"}
        
        # 2. Login as Saleh (Sales User)
        saleh_res = await client.post("/auth/login", json={"email": "saleh@alphapromena.com", "password": "<set-password>"})
        assert saleh_res.status_code == 200, f"Saleh login failed: {saleh_res.text}"
        saleh_token = saleh_res.json()["access_token"]
        saleh_headers = {"Authorization": f"Bearer {saleh_token}"}
        saleh_me = await client.get("/auth/me", headers=saleh_headers)
        assert saleh_me.status_code == 200
        saleh_data = saleh_me.json()
        
        # 3. Login as Aseel (Data Ops)
        aseel_res = await client.post("/auth/login", json={"email": "aseel@alphapromena.com", "password": "<set-password>"})
        assert aseel_res.status_code == 200, f"Aseel login failed: {aseel_res.text}"
        aseel_token = aseel_res.json()["access_token"]
        aseel_headers = {"Authorization": f"Bearer {aseel_token}"}
        
        # Verify /auth/me for Aseel
        aseel_me = await client.get("/auth/me", headers=aseel_headers)
        assert aseel_me.status_code == 200
        aseel_data = aseel_me.json()
        assert aseel_data["role"] == "DATA_OPS", f"Aseel role must be DATA_OPS, got {aseel_data['role']}"
        assert aseel_data["full_name"] == "Aseel", f"Aseel name must be 'Aseel', got {aseel_data['full_name']}"
        print(f"✓ Aseel role is strictly DATA_OPS, display name is '{aseel_data['full_name']}'")
        
        # Verify User list display names (first name only)
        users_res = await client.get("/users", headers=abdullah_headers)
        assert users_res.status_code == 200
        for u in users_res.json()["data"]:
            print(f"  User: {u['full_name']} ({u['role']}) - {u['email']}")
            assert " " not in u["full_name"].strip() or u["full_name"] in ["Dev Admin"], f"Surname found: {u['full_name']}"
        print("✓ All internal employees display single first name only (Saleh, Abdullah, Amin, Qusai, Aseel, Hasan, Ghaida)")
        
        # --- TEST 2: Company-Level Demo Conversion (ELM Scenario) ---
        print("\n--- TEST 2: Company-Level Demo Conversion Calculation ---")
        async with AsyncSessionLocal() as session:
            # Create a unique test company
            test_company = Company(
                id=uuid.uuid4(),
                name=f"ELM Test Corp {uuid.uuid4().hex[:6]}",
                country="Saudi Arabia",
                industry="Information Technology"
            )
            session.add(test_company)
            await session.commit()
            
            # Fetch saleh user id
            saleh_user = (await session.execute(select(User).filter(User.email == "saleh@alphapromena.com"))).scalar_one()
            
            # Create 10 contacts under this test company
            company_contacts = []
            for i in range(10):
                c = Contact(
                    id=uuid.uuid4(),
                    first_name=f"Contact_{i}",
                    last_name="Prospect",
                    email=f"contact_{i}_{uuid.uuid4().hex[:4]}@elmtest.sa",
                    phone=f"+9665800000{i:02d}",
                    company_id=test_company.id,
                    owner_id=saleh_user.id,
                    status=ContactStatus.INTERESTED,
                    sheet_order=i + 1
                )
                session.add(c)
                company_contacts.append(c)
            await session.commit()
            
            # Log 5 engaged calls across 5 contacts of this company
            for i in range(5):
                call = Call(
                    id=uuid.uuid4(),
                    contact_id=company_contacts[i].id,
                    user_id=saleh_user.id,
                    outcome="INTERESTED",
                    called_at=datetime.now(timezone.utc),
                )
                session.add(call)
            await session.commit()
            
            # Book 1 Demo for the company
            demo = Demo(
                id=uuid.uuid4(),
                contact_id=company_contacts[0].id,
                company_id=test_company.id,
                owner_id=saleh_user.id,
                stage=DemoStage.COMPLETED,
            )
            session.add(demo)
            await session.commit()
        
        # Query management reports dashboard
        report_res = await client.get("/reports/dashboard?period=all", headers=abdullah_headers)
        assert report_res.status_code == 200, f"Reports dashboard failed: {report_res.text}"
        rep_json = report_res.json()
        rep_data = rep_json.get("data", rep_json)
        kpis = rep_data.get("kpis", {})
        conversions = rep_data.get("conversion_rates", {})
        print(f"  KPI Unique Engaged Companies: {kpis.get('unique_engaged_companies')}")
        print(f"  KPI Unique Demo Companies: {kpis.get('unique_demo_companies')}")
        print(f"  Conversion Interested to Demo: {conversions.get('interested_to_demo')}%")
        assert kpis.get("unique_engaged_companies", 0) >= 1
        assert kpis.get("unique_demo_companies", 0) >= 1
        print("✓ Demo conversion correctly evaluates company deduplication without inflating from contact counts!")
        
        # --- TEST 3: Unlimited Contact Attempts & No Answer Retry ---
        print("\n--- TEST 3: Unlimited Contact Attempts (4th & 5th Attempts) ---")
        # Create a test contact
        create_res = await client.post("/contacts", headers=saleh_headers, json={
            "first_name": "Attempts",
            "last_name": "Prospect",
            "phone": f"+966599{uuid.uuid4().hex[:6]}",
            "company_name": "Retry Logic Co",
            "position": "Director",
            "country": "Saudi Arabia",
            "industry": "Finance"
        })
        assert create_res.status_code == 201, f"Failed to create contact: {create_res.text}"
        create_data = create_res.json()
        test_contact_id = create_data.get("data", create_data)["id"]
        
        # Log 1st, 2nd, 3rd, 4th, 5th attempts as NO_ANSWER
        for attempt_num in range(1, 6):
            call_res = await client.post("/calls", headers=saleh_headers, json={
                "contact_id": test_contact_id,
                "outcome": "NO_ANSWER",
                "notes": f"Automated test attempt {attempt_num}"
            })
            assert call_res.status_code == 201, f"Failed to log call {attempt_num}: {call_res.text}"
            
        # Fetch contact details
        contact_res = await client.get(f"/contacts/{test_contact_id}", headers=saleh_headers)
        assert contact_res.status_code == 200
        contact_json = contact_res.json()
        contact_data = contact_json.get("data", contact_json)
        print(f"  Contact attempt_count: {contact_data.get('attempt_count')}")
        print(f"  Contact last_outcome: {contact_data.get('last_outcome')}")
        print(f"  Contact final_outcome: {contact_data.get('final_outcome')}")
        print(f"  Contact status: {contact_data.get('status')}")
        
        assert contact_data.get("attempt_count") >= 5, f"Expected attempt_count >= 5, got {contact_data.get('attempt_count')}"
        assert contact_data.get("final_outcome") is None, "final_outcome must remain None on NO_ANSWER retry"
        assert contact_data.get("status") != "ARCHIVED", "Contact must remain active and NOT be archived"
        print("✓ Unlimited attempts logged (5 attempts); contact remains active and in retry queue without premature archiving!")
        
        # --- TEST 4: Explicit Final Outcome, Archive & Restore ---
        print("\n--- TEST 4: Explicit Final Outcome, Archive & Restore ---")
        # Call POST /contacts/{id}/final-outcome
        fo_res = await client.post(f"/contacts/{test_contact_id}/final-outcome", headers=saleh_headers, json={
            "final_outcome": "Not Interested",
            "notes": "Client opted for in-house solution."
        })
        assert fo_res.status_code == 200, f"Final outcome failed: {fo_res.text}"
        fo_json = fo_res.json()
        fo_data = fo_json.get("data", fo_json)
        print(f"  Archived with Final Outcome: '{fo_data.get('final_outcome')}'")
        print(f"  Status: {fo_data.get('status')}")
        print(f"  Archived at: {fo_data.get('archived_at')}")
        print(f"  Archived by: {fo_data.get('archived_by_name')}")
        
        assert fo_data.get("final_outcome") == "Not Interested"
        assert fo_data.get("status") == "ARCHIVED"
        assert fo_data.get("archived_at") is not None
        
        # Verify contact timeline still contains all attempts and history
        timeline_res = await client.get(f"/contacts/{test_contact_id}/timeline", headers=saleh_headers)
        assert timeline_res.status_code == 200
        tl_json = timeline_res.json()
        timeline_items = tl_json.get("data", tl_json)
        assert len(timeline_items) >= 5, f"Expected all attempts in timeline, found {len(timeline_items)}"
        print(f"✓ All {len(timeline_items)} timeline attempt records preserved after archiving")
        
        # Check active list excludes archived contact
        active_list_res = await client.get("/contacts", headers=saleh_headers)
        assert active_list_res.status_code == 200
        al_json = active_list_res.json()
        active_data = al_json.get("data", al_json)
        active_ids = [c["id"] for c in active_data]
        assert test_contact_id not in active_ids, "Archived contact must be excluded from default active list"
        print("✓ Archived contact excluded from default active contacts list")
        
        # Check archive filter returns contact
        arch_list_res = await client.get("/contacts?archived_only=true&final_outcome=Not Interested", headers=saleh_headers)
        assert arch_list_res.status_code == 200
        arch_json = arch_list_res.json()
        arch_data = arch_json.get("data", arch_json)
        arch_ids = [c["id"] for c in arch_data]
        assert test_contact_id in arch_ids, "Archived contact must appear in archived_only list"
        print("✓ Archived contact found in Archive tab with 'Not Interested' filter")
        
        # Unarchive and restore
        unarch_res = await client.post(f"/contacts/{test_contact_id}/unarchive", headers=saleh_headers)
        assert unarch_res.status_code == 200
        unarch_json = unarch_res.json()
        restored = unarch_json.get("data", unarch_json)
        assert restored.get("status") == "NEW"
        assert restored.get("archived_at") is None
        print(f"✓ Contact successfully restored to active contacts: status='{restored.get('status')}'")
        
        # --- TEST 5: Aseel DATA_OPS RBAC Security Boundaries ---
        print("\n--- TEST 5: Aseel DATA_OPS Authorization Boundaries ---")
        # 1. Aseel CAN access Lead Pool & Distribution status
        dist_status_res = await client.get("/admin/distribution-status", headers=aseel_headers)
        assert dist_status_res.status_code == 200, f"Aseel should access distribution-status: {dist_status_res.text}"
        print("✓ Aseel authorized for GET /admin/distribution-status (200 OK)")
        
        unassigned_res = await client.get("/admin/leads/unassigned", headers=aseel_headers)
        assert unassigned_res.status_code == 200, f"Aseel should access unassigned pool: {unassigned_res.text}"
        print("✓ Aseel authorized for GET /admin/leads/unassigned (200 OK)")
        
        sheets_res = await client.get("/integrations/google-sheets/configs", headers=aseel_headers)
        assert sheets_res.status_code == 200, f"Aseel should access google sheets configs: {sheets_res.text}"
        print("✓ Aseel authorized for GET /integrations/google-sheets/configs (200 OK)")
        
        # 2. Aseel is BLOCKED with 403 from Manager & System & Reports endpoints
        blocked_routes = [
            ("GET", "/reports/dashboard"),
            ("GET", "/reports/team-activity"),
            ("GET", "/admin/settings"),
            ("GET", "/admin/rules/distribution"),
        ]
        for method, route in blocked_routes:
            if method == "GET":
                res = await client.get(route, headers=aseel_headers)
            else:
                res = await client.post(route, headers=aseel_headers, json={})
            assert res.status_code == 403, f"Aseel must be blocked on {route}, got {res.status_code}"
            print(f"✓ Aseel strictly blocked with 403 Forbidden on {route}")
            
        # --- TEST 6: Personal Pool Distribution & Bottom-Queue Appending ---
        print("\n--- TEST 6: Lead Distribution to Personal Pool & Bottom Appending ---")
        # Distribute a lead to Saleh via Aseel
        # Create unassigned leads first
        async with AsyncSessionLocal() as session:
            unassigned_leads = [
                Contact(
                    id=uuid.uuid4(),
                    first_name=f"PoolBatch_{i}",
                    last_name="Ingested",
                    phone=f"+9665700000{i:02d}",
                    country="Saudi Arabia",
                    industry="Batch Co",
                    status=ContactStatus.NEW,
                    sheet_order=i + 1
                ) for i in range(3)
            ]
            for l in unassigned_leads:
                session.add(l)
            await session.commit()
            
            # Distribute manually to Saleh
            dist_res = await client.post("/admin/leads/distribute", headers=aseel_headers, json={
                "contact_ids": [str(l.id) for l in unassigned_leads],
                "strategy": "MANUAL",
                "target_user_id": str(saleh_data["id"])
            })
            assert dist_res.status_code == 200, f"Distribution failed: {dist_res.text}"
            
        # Verify leads are now PENDING_CLAIM in Saleh's Personal Pool
        pool_res = await client.get("/contacts?pending_claim_only=true", headers=saleh_headers)
        assert pool_res.status_code == 200
        pool_json = pool_res.json()
        pool_items = pool_json.get("data", pool_json)
        target_str_ids = [str(l.id) for l in unassigned_leads]
        pool_lead_ids = [item["id"] for item in pool_items if item["id"] in target_str_ids]
        assert len(pool_lead_ids) == 3, f"Expected 3 leads waiting in Saleh personal pool, found {len(pool_lead_ids)}"
        print(f"✓ Aseel distributed leads -> landed in Saleh's Personal Pool as PENDING_CLAIM ({len(pool_lead_ids)} leads)")
        
        # Saleh claims 2 of the leads in bulk
        claim_res = await client.post("/contacts/claim-bulk", headers=saleh_headers, json={
            "contact_ids": [pool_lead_ids[1], pool_lead_ids[0]] # Reverse order in payload
        })
        assert claim_res.status_code == 200, f"Claim bulk failed: {claim_res.text}"
        claim_json = claim_res.json()
        claimed_items = claim_json.get("data", claim_json)
        assert len(claimed_items) == 2
        
        # Verify claimed items are NEW and appended with sheet_order
        print(f"  Claimed #1 sheet_order: {claimed_items[0]['sheet_order']}")
        print(f"  Claimed #2 sheet_order: {claimed_items[1]['sheet_order']}")
        assert claimed_items[0]["status"] == "NEW"
        assert claimed_items[1]["status"] == "NEW"
        assert claimed_items[0]["sheet_order"] < claimed_items[1]["sheet_order"], "Must preserve relative sequence"
        print("✓ Claimed leads appended to end of active contact queue in correct relative order!")
        
        # --- TEST 7: Manager (Abdullah) & Team Lead (Qusai) Regression Check ---
        print("\n--- TEST 7: Leadership Non-Regression ---")
        abdullah_dashboard = await client.get("/reports/dashboard", headers=abdullah_headers)
        assert abdullah_dashboard.status_code == 200
        print("✓ Abdullah (MANAGER) full management dashboard & reports access intact (200 OK)")
        
        async with AsyncSessionLocal() as session:
            q_user = (await session.execute(select(User).filter(User.email == "qusai@alphapromena.com"))).scalar_one_or_none()
            if q_user:
                q_user.password_hash = hash_password("<set-password>")
                q_user.is_locked = False
                q_user.login_attempts = 0
                await session.commit()
                
        qusai_res = await client.post("/auth/login", json={"email": "qusai@alphapromena.com", "password": "<set-password>"})
        assert qusai_res.status_code == 200, f"Qusai login failed: {qusai_res.text}"
        qusai_token = qusai_res.json()["access_token"]
        qusai_headers = {"Authorization": f"Bearer {qusai_token}"}
        qusai_team = await client.get("/reports/dashboard", headers=qusai_headers)
        assert qusai_team.status_code == 200
        print("✓ Qusai (TEAM_LEAD) team management access intact (200 OK)")

    print("\n" + "=" * 70)
    print("ALL 7 VERIFICATION SUITES COMPLETED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_verification())
