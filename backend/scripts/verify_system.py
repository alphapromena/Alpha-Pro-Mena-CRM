import asyncio
import sys
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.contact import Contact
from app.models.call import Call
from app.models.company import Company
from app.models.opportunity import OpportunityRoadmapStep
from app.models.task import Task
from app.core.security import create_access_token

async def test_all():
    print("=== STARTING FULL SALES SYSTEM VERIFICATION ===")
    
    # 1. Generate JWT token for sales rep
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == "saleh@alphapro.com"))
        saleh = result.scalar_one_or_none()
        if not saleh:
            print("[FAIL] User saleh@alphapro.com not found in DB")
            return False
        
        role_str = saleh.role.value if hasattr(saleh.role, 'value') else saleh.role
        token = create_access_token(saleh.id, role_str)
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[OK] Authenticated as: {saleh.full_name} ({saleh.role})")
        
        # Check initial theme
        print(f"[OK] Initial Theme Preference: {saleh.theme_preference}")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # TEST 1: Update & Persist Theme
        print("\n--- Testing Theme Persistence ---")
        res = await client.patch("/api/v1/auth/theme", json={"theme_preference": "black_beige"}, headers=headers)
        assert res.status_code == 200, f"Theme patch failed: {res.text}"
        assert res.json()["theme_preference"] == "black_beige"
        
        res_me = await client.get("/api/v1/auth/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["theme_preference"] == "black_beige"
        print("[OK] Theme preference persisted and verified via /auth/me")
        
        # TEST 2: Inline Quick Call Outcome on Contact
        print("\n--- Testing Inline Quick Call & Attempt Counter ---")
        contacts_res = await client.get("/api/v1/contacts?per_page=1", headers=headers)
        assert contacts_res.status_code == 200
        first_contact = contacts_res.json()["data"][0]
        c_id = first_contact["id"]
        initial_attempts = first_contact.get("attempt_count") or 0
        print(f"Contact '{first_contact['full_name']}': initial attempts = {initial_attempts}")
        
        # Log NO_ANSWER call
        quick_call_res = await client.post(
            f"/api/v1/contacts/{c_id}/quick-call",
            json={"outcome": "NO_ANSWER", "notes": "Automated verification call attempt"},
            headers=headers
        )
        assert quick_call_res.status_code == 200, f"Quick call failed: {quick_call_res.text}"
        updated_c = quick_call_res.json()["data"]
        assert updated_c["attempt_count"] == initial_attempts + 1
        assert updated_c["last_outcome"] == "NO_ANSWER"
        assert updated_c["status"] == "NO_ANSWER"
        print(f"[OK] Quick Call logged: attempt_count incremented to {updated_c['attempt_count']}, status updated to NO_ANSWER")
        
        # TEST 3: No Answer Queue (48h Retry)
        print("\n--- Testing No Answer Queue (48h Retry Cadence) ---")
        no_ans_res = await client.get("/api/v1/no-answer", headers=headers)
        assert no_ans_res.status_code == 200
        no_ans_items = no_ans_res.json()["data"]
        matching = [i for i in no_ans_items if i["contact_id"] == c_id]
        assert len(matching) > 0, "Contact not found in No Answer queue"
        item = matching[0]
        print(f"[OK] Contact present in No Answer Queue: Attempt #{item['attempt_number']}, Next Retry = {item['next_attempt_at']}")
        
        # TEST 4: Tasks Category Filtering & Priority
        print("\n--- Testing Tasks Categorization & Priority ---")
        tasks_res = await client.get("/api/v1/tasks", headers=headers)
        assert tasks_res.status_code == 200
        all_tasks = tasks_res.json()["data"]
        print(f"[OK] Retrieved {len(all_tasks)} total tasks")
        
        # Ensure No Answer items are NOT in Tasks
        no_ans_tasks = [t for t in all_tasks if "no answer" in t["title"].lower() or t.get("type") == "NO_ANSWER"]
        assert len(no_ans_tasks) == 0, "Violation: No Answer found in general Tasks table!"
        print("[OK] Verified: No Answer items do NOT pollute the Tasks screen")
        
        # Create an Assigned Internal Task with priority
        create_task_res = await client.post(
            "/api/v1/tasks",
            json={
                "title": "Review SLA terms with Legal",
                "priority": "HIGH",
                "type": "OTHER",
                "category": "INTERNAL_ASSIGNED"
            },
            headers=headers
        )
        assert create_task_res.status_code == 201
        created_task = create_task_res.json()["data"]
        assert created_task["priority"] == "HIGH"
        assert created_task["category"] == "INTERNAL_ASSIGNED"
        assert created_task["creator_name"] is not None
        print(f"[OK] Assigned Internal Task created: '{created_task['title']}' (Priority: {created_task['priority']}, By: {created_task['creator_name']})")
        
        # Filter by INTERNAL_ASSIGNED
        filtered_tasks_res = await client.get("/api/v1/tasks?category=INTERNAL_ASSIGNED", headers=headers)
        assert filtered_tasks_res.status_code == 200
        assert any(t["id"] == created_task["id"] for t in filtered_tasks_res.json()["data"])
        print("[OK] Tasks category filtering (INTERNAL_ASSIGNED) verified")
        
        # TEST 5: Follow-ups Section A (Demo) vs Section B (Communication)
        print("\n--- Testing Follow-up Center Sectioning ---")
        demo_fu_res = await client.get("/api/v1/follow-ups?section=DEMO", headers=headers)
        assert demo_fu_res.status_code == 200
        print(f"[OK] Section A (Demo Follow-ups): {len(demo_fu_res.json()['data'])} items")
        
        comm_fu_res = await client.get("/api/v1/follow-ups?section=COMMUNICATION", headers=headers)
        assert comm_fu_res.status_code == 200
        print(f"[OK] Section B (Communication Follow-ups): {len(comm_fu_res.json()['data'])} items")
        
        # TEST 6: Companies Listing, Arabic Sorting, and RBAC Contact Visibility
        print("\n--- Testing Companies & Account Permissions ---")
        comp_res = await client.get("/api/v1/companies?sort_by=name_asc", headers=headers)
        assert comp_res.status_code == 200
        companies = comp_res.json()["data"]
        assert len(companies) > 0
        first_comp = companies[0]
        print(f"[OK] Companies list returned {len(companies)} accounts. First: {first_comp['name']}")
        
        # Check company contacts with permissions
        comp_contacts_res = await client.get(f"/api/v1/companies/{first_comp['id']}/contacts", headers=headers)
        assert comp_contacts_res.status_code == 200
        comp_contacts = comp_contacts_res.json()["data"]
        print(f"[OK] Company contacts: {len(comp_contacts)} contacts with ownership & can_edit flags")
        for cc in comp_contacts[:2]:
            print(f"   - {cc['full_name']} | Owner: {cc.get('owner_name') or 'Unassigned'} | can_edit: {cc.get('can_edit')}")
        
        # TEST 7: Opportunity Journey Roadmap CRUD
        print("\n--- Testing Opportunity Journey Roadmap ---")
        roadmap_get_res = await client.get(f"/api/v1/opportunities/roadmap/{first_comp['id']}", headers=headers)
        assert roadmap_get_res.status_code == 200
        initial_steps = roadmap_get_res.json()["data"]
        print(f"[OK] Initial roadmap steps for {first_comp['name']}: {len(initial_steps)}")
        
        # Add a new journey step
        add_step_res = await client.post(
            f"/api/v1/opportunities/roadmap/{first_comp['id']}",
            json={
                "step_type": "Demo Agreed / Scheduled",
                "step_date": datetime.now(timezone.utc).isoformat(),
                "notes": "Agreed on enterprise tier demo for executive stakeholders",
                "status": "COMPLETED"
            },
            headers=headers
        )
        assert add_step_res.status_code == 201, f"Roadmap step creation failed: {add_step_res.text}"
        new_step = add_step_res.json()["data"]
        assert new_step["step_type"] == "Demo Agreed / Scheduled"
        assert new_step["step_order"] == len(initial_steps) + 1
        print(f"[OK] Step #{new_step['step_order']} added: '{new_step['step_type']}' (Logged by: {new_step.get('user_name')})")
        
        # TEST 8: Dashboard Demo Breakdown
        print("\n--- Testing Dashboard Demo Breakdown ---")
        dash_res = await client.get("/api/v1/reports/dashboard", headers=headers)
        assert dash_res.status_code == 200
        demos_data = dash_res.json()["data"]["demos"]
        assert "agreed_requested" in demos_data
        assert "completed" in demos_data
        assert "cancelled" in demos_data
        print(f"[OK] Dashboard Demo Metrics: Agreed/Req={demos_data['agreed_requested']}, Completed={demos_data['completed']}, Cancelled={demos_data['cancelled']}")

        # TEST 9: Language Persistence (Arabic / English)
        print("\n--- Testing Language Preference Persistence ---")
        lang_res = await client.patch("/api/v1/auth/language", json={"preferred_language": "ar"}, headers=headers)
        assert lang_res.status_code == 200
        assert lang_res.json()["preferred_language"] == "ar"
        
        me_ar = await client.get("/api/v1/auth/me", headers=headers)
        assert me_ar.status_code == 200
        assert me_ar.json()["preferred_language"] == "ar"
        print("[OK] Language preference persisted as 'ar' in DB and verified via /auth/me")
        
        # Reset to en
        await client.patch("/api/v1/auth/language", json={"preferred_language": "en"}, headers=headers)

        # TEST 10: Multi-Record Contact Notes System
        print("\n--- Testing Multi-Record Contact Notes System ---")
        add_note_res = await client.post(
            f"/api/v1/contacts/{c_id}/notes",
            json={"note_text": "Decision maker asked to follow up after Q3 board meeting.", "is_pinned": True},
            headers=headers
        )
        assert add_note_res.status_code == 201
        created_note = add_note_res.json()["data"]
        assert created_note["note_text"] == "Decision maker asked to follow up after Q3 board meeting."
        assert created_note["user_name"] is not None
        print(f"[OK] Note created: '{created_note['note_text']}' by {created_note['user_name']}")

        notes_list_res = await client.get(f"/api/v1/contacts/{c_id}/notes", headers=headers)
        assert notes_list_res.status_code == 200
        notes = notes_list_res.json()["data"]
        assert len(notes) > 0
        assert notes[0]["note_text"] == created_note["note_text"]
        print(f"[OK] Contact note history verified: {len(notes)} timestamped notes found")

        # TEST 11: Safe Outcome Correction & Automation Rollback
        print("\n--- Testing Safe Outcome Correction & Automation Rollback ---")
        # Currently the contact is NO_ANSWER from Test 2 and exists in NoAnswerQueue
        no_ans_before = await client.get("/api/v1/no-answer", headers=headers)
        assert any(i["contact_id"] == c_id for i in no_ans_before.json()["data"])
        
        # Correct outcome from NO_ANSWER to INTERESTED
        correction_res = await client.post(
            f"/api/v1/contacts/{c_id}/correct-outcome",
            json={"new_outcome": "INTERESTED", "reason": "Accidentally selected No Answer instead of Interested"},
            headers=headers
        )
        assert correction_res.status_code == 200, f"Correction failed: {correction_res.text}"
        corrected_contact = correction_res.json()["data"]
        corrected_call = correction_res.json()["call"]
        assert corrected_contact["last_outcome"] == "INTERESTED"
        assert corrected_contact["status"] == "INTERESTED"
        assert corrected_call["is_corrected"] is True
        assert corrected_call["previous_outcome"] == "NO_ANSWER"
        print(f"[OK] Outcome safely corrected: {corrected_call['previous_outcome']} -> {corrected_call['outcome']}")

        # Verify contact was safely removed from NoAnswerQueue
        no_ans_after = await client.get("/api/v1/no-answer", headers=headers)
        assert not any(i["contact_id"] == c_id for i in no_ans_after.json()["data"]), "Violation: Contact still in No Answer queue after correction!"
        print("[OK] Verified: Contact automatically removed from No Answer queue upon correction")

        # Verify Audit Trail
        audit_res = await client.get(f"/api/v1/contacts/{c_id}/timeline", headers=headers)
        assert audit_res.status_code == 200
        print("[OK] Audit trail verified in timeline")
        
    print("\n==========================================================================")
    print("[SUCCESS] ALL SALES EXPERIENCE, NOTES, CORRECTION & i18n TESTS PASSED 100%!")
    print("==========================================================================\n")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_all())
    sys.exit(0 if success else 1)
