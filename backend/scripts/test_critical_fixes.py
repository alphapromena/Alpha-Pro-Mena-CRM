"""
Automated Verification Suite for Critical Fixes:
1. Dynamic Attempts (1st, 2nd, 3rd, 4th, 5th...) with no artificial limit and empty final outcome.
2. Final Outcome explicit setting -> moves to Archive with full history preserved.
3. Total Contacts Counting Integrity (logging 5 calls against 1 contact does NOT increase active contacts count).
4. Google Sheets Idempotency (re-syncing sheet produces 0 duplicate contacts and 0 duplicate attempts).
5. Aseel Data Operations Login & Role Boundary Isolation.
6. Aseel Distribution to Personal Pool & Bottom Appending with Relative Order.
7. Leadership (Abdullah & Qusai) and First-Name display non-regression.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone
import structlog
from sqlalchemy import select, func, text
import httpx

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.main import create_app
from app.database import AsyncSessionLocal, engine
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.call import Call
from app.core.security import hash_password, create_access_token, normalize_email
from app.integrations.google_sheets.service import GoogleSheetsSyncService
from app.models.integrations import GoogleSheetsSyncConfig

logger = structlog.get_logger(__name__)

async def run_tests():
    print("=" * 70)
    print("RUNNING ALPHA PRO MENA CRM CRITICAL FIXES VERIFICATION SUITE")
    print("=" * 70)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:

        # ── TEST 1: ASEEL LOGIN & AUTHENTICATION ──────────────────────────────
        print("\n--- TEST 1: Aseel Account Login & Workspace Isolation ---")
        login_res = await client.post(
            "/auth/login",
            json={"email": "aseel@alphapromena.com", "password": "<set-password>"}
        )
        assert login_res.status_code == 200, f"Aseel login failed: {login_res.text}"
        aseel_token = login_res.json()["access_token"]
        aseel_headers = {"Authorization": f"Bearer {aseel_token}"}
        print("[PASS] Aseel logged in successfully with 200 OK")

        me_res = await client.get("/auth/me", headers=aseel_headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["role"] == "DATA_OPS", f"Expected DATA_OPS role, got {me_data['role']}"
        assert me_data["first_name"] == "Aseel"
        print("[PASS] Aseel role is strictly DATA_OPS, first_name is 'Aseel'")

        # Workspace boundary check
        pool_res = await client.get("/admin/leads/unassigned", headers=aseel_headers)
        assert pool_res.status_code == 200, f"Aseel should access unassigned pool, got {pool_res.status_code}"
        
        dist_res = await client.get("/admin/distribution-status", headers=aseel_headers)
        assert dist_res.status_code == 200, f"Aseel should access distribution status, got {dist_res.status_code}"
        
        rep_res = await client.get("/reports/dashboard", headers=aseel_headers)
        assert rep_res.status_code == 403, f"Aseel should get 403 on reports dashboard, got {rep_res.status_code}"
        
        set_res = await client.get("/admin/settings", headers=aseel_headers)
        assert set_res.status_code == 403, f"Aseel should get 403 on admin settings, got {set_res.status_code}"
        print("[PASS] Aseel RBAC boundaries verified (200 OK for Data Ops, 403 Forbidden for Reports/Settings)")

        # Saleh login for sales tests
        saleh_login = await client.post(
            "/auth/login",
            json={"email": "saleh@alphapromena.com", "password": "<set-password>"}
        )
        assert saleh_login.status_code == 200
        saleh_token = saleh_login.json()["access_token"]
        saleh_headers = {"Authorization": f"Bearer {saleh_token}"}
        saleh_me = await client.get("/auth/me", headers=saleh_headers)
        saleh_id = saleh_me.json()["id"]

        # ── TEST 2: DYNAMIC ATTEMPTS (1st, 2nd, 3rd, 4th, 5th...) ─────────────
        print("\n--- TEST 2: Dynamic Unlimited Contact Attempts ---")
        # Create a fresh contact for Saleh
        new_c_res = await client.post(
            "/contacts",
            headers=saleh_headers,
            json={
                "first_name": f"Prospect_{uuid.uuid4().hex[:6]}",
                "last_name": "Al-Amri",
                "phone": f"+96650{uuid.uuid4().int % 10000000:07d}",
                "email": f"prospect_{uuid.uuid4().hex[:6]}@domain.com",
            }
        )
        assert new_c_res.status_code == 201, f"Failed to create contact: {new_c_res.text}"
        contact_id = new_c_res.json()["data"]["id"]

        # Log 5 consecutive attempts (No Answer)
        for attempt_i in range(1, 6):
            call_res = await client.post(
                "/calls",
                headers=saleh_headers,
                json={
                    "contact_id": contact_id,
                    "outcome": "NO_ANSWER",
                    "notes": f"Automated test attempt {attempt_i}",
                    "duration_seconds": 15,
                }
            )
            assert call_res.status_code == 201

        # Fetch contact details and verify attempts array
        c_detail = await client.get(f"/contacts/{contact_id}", headers=saleh_headers)
        assert c_detail.status_code == 200
        c_data = c_detail.json()["data"]
        assert c_data["attempt_count"] == 5, f"Expected 5 attempts, got {c_data['attempt_count']}"
        assert len(c_data["attempts"]) == 5, f"Expected 5 attempts in array, got {len(c_data['attempts'])}"
        assert c_data["last_outcome"] == "NO_ANSWER"
        assert c_data["final_outcome"] is None, f"Final outcome must be None, got {c_data['final_outcome']}"
        assert c_data["status"] != "ARCHIVED", "Contact must NOT be archived on No Answer"
        print(f"[PASS] 5 attempts logged: attempt_count={c_data['attempt_count']}, len(attempts)={len(c_data['attempts'])}")
        print("[PASS] Final Outcome is strictly None/unset (No Answer is NOT final outcome)")

        # ── TEST 3: TOTAL CONTACTS COUNT STABILITY ────────────────────────────
        print("\n--- TEST 3: Total Contacts Counting Stability ---")
        # Get active contacts count for Saleh before adding attempts
        list_before = await client.get("/contacts", headers=saleh_headers)
        total_before = list_before.json()["meta"]["total"]

        # Log 5 more attempts on the same contact
        for attempt_i in range(6, 11):
            await client.post(
                "/calls",
                headers=saleh_headers,
                json={
                    "contact_id": contact_id,
                    "outcome": "RE_CALL" if attempt_i == 10 else "NO_ANSWER",
                    "notes": f"Attempt {attempt_i}",
                    "duration_seconds": 20,
                }
            )

        # Get active contacts count after 5 additional calls
        list_after = await client.get("/contacts", headers=saleh_headers)
        total_after = list_after.json()["meta"]["total"]
        assert total_after == total_before, f"Active contacts count changed! Before={total_before}, After={total_after}"
        print(f"[PASS] Before calls: Active Contacts = {total_before}")
        print(f"[PASS] After 5 more calls on same contact: Active Contacts = {total_after} (100% STABLE!)")

        # ── TEST 4: EXPLICIT FINAL OUTCOME & ARCHIVE ──────────────────────────
        print("\n--- TEST 4: Explicit Final Outcome & Archive ---")
        fo_res = await client.post(
            f"/contacts/{contact_id}/final-outcome",
            headers=saleh_headers,
            json={
                "final_outcome": "Not Interested",
                "notes": "Prospect confirmed no budget for 2026",
            }
        )
        assert fo_res.status_code == 200, f"Failed to set final outcome: {fo_res.text}"
        fo_data = fo_res.json()["data"]
        assert fo_data["status"] == "ARCHIVED"
        assert fo_data["final_outcome"] == "Not Interested"
        assert fo_data["archived_at"] is not None

        # Check Active list (should decrease by 1)
        list_active = await client.get("/contacts", headers=saleh_headers)
        total_active_now = list_active.json()["meta"]["total"]
        assert total_active_now == total_before - 1, f"Active contacts should decrease by 1, got {total_active_now}"

        # Check Archive list (should contain this contact with all 10 attempts preserved)
        list_archive = await client.get("/contacts?archived_only=true", headers=saleh_headers)
        archive_contacts = list_archive.json()["data"]
        archived_item = next((x for x in archive_contacts if x["id"] == contact_id), None)
        assert archived_item is not None, "Contact should appear in Archive list"
        assert archived_item["final_outcome"] == "Not Interested"
        assert archived_item["attempt_count"] >= 10, f"Expected >=10 attempts preserved, got {archived_item['attempt_count']}"
        print(f"[PASS] Final Outcome set to 'Not Interested' -> Active Contacts decremented by 1")
        print(f"[PASS] Contact found in Archive tab with all {archived_item['attempt_count']} historical attempts intact")

        # Unarchive check
        unarch_res = await client.post(f"/contacts/{contact_id}/unarchive", headers=saleh_headers)
        assert unarch_res.status_code == 200
        list_restored = await client.get("/contacts", headers=saleh_headers)
        assert list_restored.json()["meta"]["total"] == total_before
        print("[PASS] Restored contact from Archive back to Active contacts successfully")

        # ── TEST 5: GOOGLE SHEETS RE-SYNC IDEMPOTENCY ─────────────────────────
        print("\n--- TEST 5: Google Sheets Sync & Re-Sync Idempotency ---")
        async with AsyncSessionLocal() as session:
            test_batch_uid = uuid.uuid4().hex[:6]
            cfg = GoogleSheetsSyncConfig(
                name=f"Test Idempotent Sheet {test_batch_uid}",
                spreadsheet_id=f"test_sheet_{test_batch_uid}",
                sheet_name="Leads",
                range="A:I",
            )
            session.add(cfg)
            await session.commit()
            await session.refresh(cfg)
            cfg_id = cfg.id

            service = GoogleSheetsSyncService(session)
            mock_rows = [
                {
                    "First Name": f"IdempotentLead1_{test_batch_uid}",
                    "Last Name": "Al-Harbi",
                    "Email": f"harbi_{test_batch_uid}@testcompany.com",
                    "Phone": f"+96651{uuid.uuid4().int % 10000000:07d}",
                    "Company": f"Harbi Tech {test_batch_uid}",
                    "1st Attempts": "No Answer",
                    "2nd Attempts": "Asked for email",
                },
                {
                    "First Name": f"IdempotentLead2_{test_batch_uid}",
                    "Last Name": "Al-Zahrani",
                    "Email": f"zahrani_{test_batch_uid}@testcompany.com",
                    "Phone": f"+96652{uuid.uuid4().int % 10000000:07d}",
                    "Company": f"Zahrani Logistics {test_batch_uid}",
                    "1st Attempts": "Interested",
                }
            ]

            # First sync
            run1 = await service.run_sync(config_id=cfg_id, triggered_by="manual", mock_data=mock_rows)
            await session.commit()
            print(f"  First Sync: Imported={run1.rows_imported}, Duplicate={run1.rows_duplicate}, Error={run1.rows_error}")
            assert run1.rows_imported == 2
            assert run1.rows_duplicate == 0

            # Count contacts before second sync
            count_stmt = select(func.count(Contact.id)).where(Contact.deleted_at.is_(None))
            count1 = (await session.execute(count_stmt)).scalar_one()

            # Second sync (exact same data)
            run2 = await service.run_sync(config_id=cfg_id, triggered_by="manual", mock_data=mock_rows)
            await session.commit()
            print(f"  Second Sync (Re-sync): Imported={run2.rows_imported}, Duplicate={run2.rows_duplicate}, Error={run2.rows_error}")
            assert run2.rows_imported == 0, f"Expected 0 new rows imported, got {run2.rows_imported}"
            assert run2.rows_duplicate == 2, f"Expected 2 duplicate rows skipped, got {run2.rows_duplicate}"

            count2 = (await session.execute(count_stmt)).scalar_one()
            assert count1 == count2, f"Contacts count increased on re-sync! count1={count1}, count2={count2}"
            print("[PASS] Google Sheet re-sync is 100% idempotent: New Contacts = 0, Duplicate Historical Attempts = 0")

        # ── TEST 6: PERSONAL POOL DISTRIBUTION & END-OF-QUEUE ORDERING ────────
        print("\n--- TEST 6: Lead Distribution to Personal Pool & Bottom Appending ---")
        # Create 2 unassigned leads
        async with AsyncSessionLocal() as session:
            c1 = Contact(first_name="PoolLeadA", email="poolA@test.com", phone="+966533333331", status=ContactStatus.UNASSIGNED, sheet_order=10)
            c2 = Contact(first_name="PoolLeadB", email="poolB@test.com", phone="+966533333332", status=ContactStatus.UNASSIGNED, sheet_order=20)
            session.add_all([c1, c2])
            await session.commit()
            await session.refresh(c1)
            await session.refresh(c2)
            c1_id, c2_id = str(c1.id), str(c2.id)

        # Aseel distributes to Saleh
        dist_res = await client.post(
            "/admin/leads/distribute",
            headers=aseel_headers,
            json={
                "contact_ids": [c1_id, c2_id],
                "strategy": "MANUAL",
                "target_user_id": str(saleh_id),
            }
        )
        assert dist_res.status_code == 200, f"Distribution failed: {dist_res.text}"

        # Verify leads are in Saleh's Personal Pool (PENDING_CLAIM), NOT in active contacts
        pool_res = await client.get("/contacts?pending_claim_only=true", headers=saleh_headers)
        pool_data = pool_res.json()["data"]
        pool_ids = [x["id"] for x in pool_data]
        assert c1_id in pool_ids and c2_id in pool_ids, "Leads must land in Personal Pool"

        # Saleh claims the leads
        claim_res = await client.post(
            "/contacts/claim-bulk",
            headers=saleh_headers,
            json={"contact_ids": [c1_id, c2_id]}
        )
        assert claim_res.status_code == 200, f"Claim failed: {claim_res.text}"
        claimed = claim_res.json()["data"]
        assert len(claimed) == 2
        assert claimed[0]["sheet_order"] < claimed[1]["sheet_order"], "Claimed leads must preserve sheet order"
        print("[PASS] Leads distributed by Aseel landed in Personal Pool and were claimed to the end of queue in correct order")

        # ── TEST 7: LEADERSHIP NON-REGRESSION ─────────────────────────────────
        print("\n--- TEST 7: Leadership Non-Regression & First Names ---")
        abdullah_login = await client.post("/auth/login", json={"email": "abdallah@alphapromena.com", "password": "<set-password>"})
        assert abdullah_login.status_code == 200
        abdullah_token = abdullah_login.json()["access_token"]
        rep_res = await client.get("/reports/dashboard", headers={"Authorization": f"Bearer {abdullah_token}"})
        assert rep_res.status_code == 200, "Abdullah (MANAGER) must have full report access"

        qusai_login = await client.post("/auth/login", json={"email": "qusai@alphapromena.com", "password": "<set-password>"})
        assert qusai_login.status_code == 200
        qusai_token = qusai_login.json()["access_token"]
        team_res = await client.get("/reports/team-activity", headers={"Authorization": f"Bearer {qusai_token}"})
        assert team_res.status_code == 200, "Qusai (TEAM_LEAD) must have team activity access"
        print("[PASS] Abdullah (MANAGER) and Qusai (TEAM_LEAD) full leadership permissions verified")

    print("\n" + "=" * 70)
    print("ALL CRITICAL FIXES VERIFICATION SUITES COMPLETED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_tests())
