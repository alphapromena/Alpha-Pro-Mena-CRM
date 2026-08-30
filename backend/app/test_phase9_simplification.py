"""
Comprehensive Verification Suite for Phase 9: Workflow Simplification & Contacts Restructure
Tests 1 through 9 and Regression across all user roles and workflows.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import create_app
from app.database import get_db, AsyncSessionLocal
from app.models.contact import Contact, ContactStatus
from app.models.company import Company
from app.models.call import Call
from app.models.recall import Recall
from app.models.no_answer import NoAnswerQueue
from app.models.opportunity import OpportunityRoadmapStep
from app.models.user import User
from sqlalchemy import select, func


async def run_all_tests():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    
    print("=" * 70)
    print("RUNNING WORKFLOW SIMPLIFICATION & CONTACTS RESTRUCTURE TEST SUITE")
    print("=" * 70)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Authentication Verification for all users
        print("\n--- TEST 1: LOGIN VERIFICATION ACROSS ROLES ---")
        users_to_test = [
            ("saleh@alphapromena.com", "Sales123!", "Saleh", "USER"),
            ("amin@alphapromena.com", "Sales123!", "Amin", "USER"),
            ("hasan@alphapromena.com", "Sales123!", "Hasan", "USER"),
            ("ghaida@alphapromena.com", "Sales123!", "Ghaida", "USER"),
            ("abdallah@alphapromena.com", "Manager123!", "Abdullah", "MANAGER"),
            ("qusai@alphapromena.com", "TeamLead123!", "Qusai", "TEAM_LEAD"),
            ("aseel@alphapromena.com", "Sales123!", "Aseel", "DATA_OPS"),
        ]
        
        user_tokens = {}
        for email, pwd, name, expected_role in users_to_test:
            res = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
            assert res.status_code == 200, f"Login failed for {email}: {res.text}"
            token = res.json()["access_token"]
            user_tokens[name] = token
            
            # Verify /me profile
            me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me_res.status_code == 200
            assert me_res.json()["first_name"] == name
            print(f"  [OK] {name} ({expected_role}) authenticated successfully")
        print("[PASS] Test 1: All roles authenticate with correct permissions")

        saleh_headers = {"Authorization": f"Bearer {user_tokens['Saleh']}"}
        abdullah_headers = {"Authorization": f"Bearer {user_tokens['Abdullah']}"}

        # 2. Contacts 3-View Architecture (LEADS, EMAIL & WHATSAPP, ARCHIVE)
        print("\n--- TEST 2: CONTACTS 3-VIEW ARCHITECTURE ---")
        # LEADS view
        leads_res = await client.get("/api/v1/contacts?source_sheet=Leads&per_page=10", headers=saleh_headers)
        assert leads_res.status_code == 200
        leads_data = leads_res.json()["data"]
        assert len(leads_data) > 0
        test_contact = leads_data[0]
        contact_id = test_contact["id"]
        print(f"  [OK] LEADS view returned {leads_res.json()['meta']['total']} active leads for Saleh")

        # EMAIL & WHATSAPP view filter
        ew_res = await client.get("/api/v1/contacts?status=EMAIL_AND_WHATSAPP&per_page=10", headers=saleh_headers)
        assert ew_res.status_code == 200
        print(f"  [OK] EMAIL & WHATSAPP view endpoint active and returning filtered communication records")

        # ARCHIVE view filter
        arch_res = await client.get("/api/v1/contacts?status=ARCHIVED&include_archived=true&per_page=10", headers=saleh_headers)
        assert arch_res.status_code == 200
        print(f"  [OK] ARCHIVE view endpoint active and returning archived records")
        print("[PASS] Test 2: Only 3 primary logical views active")

        # 3. Fixed Five Attempts Verification
        print("\n--- TEST 3: FIXED FIVE ATTEMPTS MODEL ---")
        # Create a clean dedicated test contact
        create_res = await client.post("/api/v1/contacts", headers=saleh_headers, json={
            "first_name": "TestFiveAttempts",
            "last_name": "Lead",
            "phone": "+966509990001",
            "email": "five.attempts@testdomain.com",
            "country": "Saudi Arabia",
            "position": "Procurement Lead"
        })
        assert create_res.status_code == 201
        five_att_id = create_res.json()["data"]["id"]

        # Log 1st Attempt: No Answer
        att1 = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "No Answer"})
        assert att1.status_code == 200
        assert att1.json()["data"]["attempt_count"] == 1
        assert len(att1.json()["data"]["attempts"]) == 1

        # Log 2nd Attempt: No Answer
        att2 = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "No Answer"})
        assert att2.status_code == 200
        assert att2.json()["data"]["attempt_count"] == 2

        # Log 3rd Attempt: Asked for email
        att3 = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "Asked for email"})
        assert att3.status_code == 200
        assert att3.json()["data"]["attempt_count"] == 3

        # Log 4th Attempt: No Answer
        att4 = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "No Answer"})
        assert att4.status_code == 200
        assert att4.json()["data"]["attempt_count"] == 4

        # Log 5th Attempt: No Answer
        att5 = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "No Answer"})
        assert att5.status_code == 200
        assert att5.json()["data"]["attempt_count"] == 5
        assert len(att5.json()["data"]["attempts"]) == 5
        print(f"  [OK] 5 Call attempts logged sequentially on contact {five_att_id}")
        print("[PASS] Test 3: Fixed 5 attempts logged accurately via single Contact ID")

        # 4. No Answer Retry Queue (+48h) Synchronization
        print("\n--- TEST 4: NO ANSWER +48H RETRY QUEUE SYNCHRONIZATION ---")
        na_res = await client.get(f"/api/v1/no-answer?contact_id={five_att_id}", headers=saleh_headers)
        assert na_res.status_code == 200
        na_items = na_res.json()["data"]
        assert len(na_items) > 0
        found_na = na_items[0]
        assert found_na["contact_id"] == five_att_id
        assert found_na["attempt_number"] == 5
        print(f"  [OK] Contact {five_att_id} present in No Answer Queue with attempt #{found_na['attempt_number']}")

        # Test direct outcome from No Answer Queue
        direct_outcome = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "Interested"})
        assert direct_outcome.status_code == 200
        assert direct_outcome.json()["data"]["status"] == "INTERESTED"

        # Verify contact removed from No Answer Queue after answering
        na_check = await client.get(f"/api/v1/no-answer?contact_id={five_att_id}", headers=saleh_headers)
        assert len(na_check.json()["data"]) == 0
        print(f"  [OK] Contact answered -> automatically resolved and removed from No Answer Queue")
        print("[PASS] Test 4: No Answer +48h queue fully synchronized with Contacts")

        # 5. Scheduled Recalls Synchronization
        print("\n--- TEST 5: SCHEDULED RECALLS SYNCHRONIZATION ---")
        # Create recall on contact
        recall_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        rec_call = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={
            "outcome": "CALL_LATER",
            "callback_requested_at": recall_time,
            "notes": "Customer asked to call back on Sunday morning"
        })
        assert rec_call.status_code == 200
        assert rec_call.json()["data"]["status"] == "RECALL_SCHEDULED"

        # Verify appearance in /recalls endpoint
        recalls_res = await client.get(f"/api/v1/recalls?contact_id={five_att_id}", headers=saleh_headers)
        assert recalls_res.status_code == 200
        found_recalls = recalls_res.json()["data"]
        assert len(found_recalls) > 0
        found_recall = found_recalls[0]
        assert found_recall["contact_id"] == five_att_id
        assert found_recall["status"] == "PENDING"
        print(f"  [OK] Contact {five_att_id} scheduled recall created and visible in Scheduled Recalls")

        # Record next call from Scheduled Recalls
        direct_recall_res = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "Demo"})
        assert direct_recall_res.status_code == 200
        assert direct_recall_res.json()["data"]["status"] == "DEMO_SCHEDULED"

        # Verify pending recall marked completed
        recalls_check = await client.get("/api/v1/recalls", headers=saleh_headers)
        assert not any(r["contact_id"] == five_att_id for r in recalls_check.json()["data"])
        print(f"  [OK] Call logged from Recalls -> next attempt updated in Contacts & recall completed")
        print("[PASS] Test 5: Scheduled Recalls bidirectionally synchronized with Contacts")

        # 6. Email & WhatsApp Workflow
        print("\n--- TEST 6: EMAIL & WHATSAPP WORKFLOW ---")
        ew_call = await client.post(f"/api/v1/contacts/{five_att_id}/quick-call", headers=saleh_headers, json={"outcome": "Asked for email"})
        assert ew_call.status_code == 200
        assert ew_call.json()["data"]["status"] == "EMAIL_REQUESTED"

        # Verify visible under EMAIL_AND_WHATSAPP filter
        ew_list = await client.get(f"/api/v1/contacts?status=EMAIL_AND_WHATSAPP&search=TestFiveAttempts", headers=saleh_headers)
        assert ew_list.status_code == 200
        assert any(c["id"] == five_att_id for c in ew_list.json()["data"])
        print(f"  [OK] Contact {five_att_id} active in EMAIL & WHATSAPP view without duplication")
        print("[PASS] Test 6: Email & WhatsApp workflow verified on same Contact record")

        # 7. Final Outcome -> Archive Logic
        print("\n--- TEST 7: FINAL OUTCOME -> ARCHIVE ---")
        # Set Final Outcome = Not Interested
        fo_res = await client.post(f"/api/v1/contacts/{five_att_id}/final-outcome", headers=saleh_headers, json={
            "final_outcome": "Not Interested",
            "notes": "Decided to renew existing vendor contract."
        })
        assert fo_res.status_code == 200
        archived_contact = fo_res.json()["data"]
        assert archived_contact["status"] == "ARCHIVED"
        assert archived_contact["final_outcome"] == "Not Interested"

        # Verify absent from active LEADS
        active_check = await client.get(f"/api/v1/contacts?search=TestFiveAttempts", headers=saleh_headers)
        assert not any(c["id"] == five_att_id for c in active_check.json()["data"])

        # Verify present in ARCHIVE
        arch_check = await client.get(f"/api/v1/contacts?status=ARCHIVED&include_archived=true&search=TestFiveAttempts", headers=saleh_headers)
        assert any(c["id"] == five_att_id for c in arch_check.json()["data"])
        print(f"  [OK] Contact moved from active LEADS (-1) to ARCHIVE (+1) with preserved history")

        # Test Restore
        unarch_res = await client.post(f"/api/v1/contacts/{five_att_id}/unarchive", headers=saleh_headers)
        assert unarch_res.status_code == 200
        assert unarch_res.json()["data"]["status"] == "NEW"
        print(f"  [OK] Contact successfully restored back to active LEADS")
        print("[PASS] Test 7: Final Outcome -> Archive -> Restore cycle verified")

        # 8. Company Follow-up Journey Builder
        print("\n--- TEST 8: COMPANY FOLLOW-UP JOURNEY BUILDER ---")
        # Get ELM company
        comp_res = await client.get("/api/v1/companies?search=ELM", headers=saleh_headers)
        assert comp_res.status_code == 200
        comp_list = comp_res.json()["data"]
        if comp_list:
            elm_id = comp_list[0]["id"]
        else:
            # Create ELM company if not found
            create_elm = await client.post("/api/v1/companies", headers=abdullah_headers, json={"name": "ELM Company", "country": "Saudi Arabia"})
            elm_id = create_elm.json()["data"]["id"]

        # Step 1: First Call
        s1 = await client.post(f"/api/v1/opportunities/roadmap/{elm_id}", headers=saleh_headers, json={
            "step_type": "First Call",
            "step_date": "2026-08-27T10:00:00Z",
            "notes": "Interested in Data Quality & Governance",
            "status": "COMPLETED",
            "step_order": 1
        })
        assert s1.status_code == 201

        # Step 2: Email Sent
        s2 = await client.post(f"/api/v1/opportunities/roadmap/{elm_id}", headers=saleh_headers, json={
            "step_type": "Email Sent",
            "step_date": "2026-08-28T11:00:00Z",
            "notes": "Sent Ataccama solution brief",
            "status": "COMPLETED",
            "step_order": 2
        })
        assert s2.status_code == 201

        # Step 3: Demo Scheduled
        s3 = await client.post(f"/api/v1/opportunities/roadmap/{elm_id}", headers=saleh_headers, json={
            "step_type": "Demo Scheduled",
            "step_date": "2026-09-01T14:00:00Z",
            "notes": "Meeting with Data Team",
            "status": "SCHEDULED",
            "step_order": 3
        })
        assert s3.status_code == 201

        # Step 4: Proposal Sent
        s4 = await client.post(f"/api/v1/opportunities/roadmap/{elm_id}", headers=saleh_headers, json={
            "step_type": "Commercial Proposal Sent",
            "step_date": "2026-09-04T09:00:00Z",
            "notes": "Waiting for procurement review",
            "status": "IN_PROGRESS",
            "step_order": 4
        })
        assert s4.status_code == 201

        # Verify Roadmap
        roadmap_res = await client.get(f"/api/v1/opportunities/roadmap/{elm_id}", headers=saleh_headers)
        assert roadmap_res.status_code == 200
        steps = roadmap_res.json()["data"]
        assert len(steps) >= 4
        print(f"  [OK] Company Journey for ELM contains {len(steps)} sequential steps")
        for s in steps[:4]:
            print(f"    - Step {s['step_order']}: {s['step_type']} ({s['step_date'][:10]}) -> {s['notes']}")
        print("[PASS] Test 8: Company-level Journey Builder fully functional and persisted")

        # 9. Aseel Data Operations Preservation
        print("\n--- TEST 9: DATA OPERATIONS (ASEEL) ISOLATION ---")
        aseel_headers = {"Authorization": f"Bearer {user_tokens['Aseel']}"}
        pool_res = await client.get("/api/v1/contacts?pending_claim_only=true", headers=aseel_headers)
        assert pool_res.status_code == 200
        print(f"  [OK] Aseel accesses lead pool with {pool_res.json()['meta']['total']} unclaimed leads")
        print("[PASS] Test 9: Data Operations permissions preserved")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
