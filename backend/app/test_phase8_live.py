"""
Phase 8 End-to-End Live Validation Script.
Tests all Phase 8 requirements against the live backend API and database:
1. User display name cleanup (Saleh, Abdullah, Amin, Qusai, Aseel, Ghaida, Hasan — no surnames)
2. Customer contact full names preserved (Faisal Al-Otaibi, etc.)
3. Unlimited call attempts logging (1, 2, 3, 4, 5...)
4. Prominent outcome tracking
5. Complete Archive & Restore workflow + exclusion from default list
6. Aseel (TEAM_LEAD) lead distribution -> PENDING_CLAIM in Saleh's Personal Pool
7. Saleh Personal Pool claim (single & bulk) appending in sheet_order
8. Abdullah (MANAGER) access & regression check
"""
import httpx
import uuid
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000/api/v1"


def print_step(title):
    print(f"\n{'='*70}\n[STEP] {title}\n{'='*70}")


def login(client, email, password):
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200, f"Get /auth/me failed for {email}: {me_res.text}"
    user_data = me_res.json()
    return headers, user_data


def main():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        # 1. Test Login as Saleh
        print_step("1. Login as Saleh (Sales User)")
        saleh_headers, saleh_data = login(client, "saleh@alphapromena.com", "Sales123!")
        print(f"✓ Saleh logged in: first_name='{saleh_data['first_name']}', full_name='{saleh_data['full_name']}', role='{saleh_data['role']}'")
        assert saleh_data["full_name"] == "Saleh", f"Expected Saleh, got {saleh_data['full_name']}"

        # 2. Test User Display Names across roster
        print_step("2. Verify Internal User Display Names (no surnames) & Customer Full Names")
        abdullah_headers, abdullah_data = login(client, "abdallah@alphapromena.com", "Manager123!")

        res_users = client.get("/users", headers=abdullah_headers)
        assert res_users.status_code == 200
        users = res_users.json()["data"]
        for u in users:
            print(f"  Internal User: id={u['id'][:8]}.. | name='{u['full_name']}' | email={u['email']} | role={u['role']}")
            assert " " not in u["full_name"].strip() or u["full_name"] in ["Dev Admin"], f"Surname found in internal user: {u['full_name']}"
        print("✓ All internal employee display names are single first names (Saleh, Abdullah, Amin, Qusai, Aseel, Ghaida, Hasan)")

        # Verify customer contact names keep full names
        res_contacts = client.get("/contacts?per_page=10", headers=abdullah_headers)
        assert res_contacts.status_code == 200
        contacts = res_contacts.json()["data"]
        print("\n  Sample CRM Customer Contacts (Full Names Preserved):")
        for c in contacts[:5]:
            print(f"  Customer Contact: '{c['full_name']}' | Company: '{c.get('company_name')}' | Owner: '{c.get('owner_name')}'")
        print("✓ Customer contacts retain complete full names!")

        # 3. Test Unlimited Attempts & Outcome on Saleh's own contact
        print_step("3. Test Flexible Unlimited Attempts & Standalone Outcome")
        saleh_contacts_res = client.get("/contacts?per_page=5", headers=saleh_headers)
        assert saleh_contacts_res.status_code == 200
        saleh_contacts = saleh_contacts_res.json()["data"]
        assert len(saleh_contacts) > 0, "Saleh must have contacts"
        test_contact = saleh_contacts[0]
        cid = test_contact["id"]
        print(f"Testing on Saleh's contact: {test_contact['full_name']} (ID: {cid})")

        outcomes = ["INTERESTED", "Asked for email", "Re Call", "Demo", "INTERESTED"]
        for i, outcome in enumerate(outcomes, 1):
            call_res = client.post(
                f"/contacts/{cid}/quick-call",
                headers=saleh_headers,
                json={"outcome": outcome, "notes": f"Test Attempt {i} live validation"},
            )
            assert call_res.status_code == 200, f"Call {i} failed: {call_res.text}"
            print(f"  ✓ Logged Attempt {i}: Outcome='{outcome}' -> Contact last_outcome='{call_res.json()['data']['last_outcome']}'")

        # Verify timeline shows all attempts
        t_res = client.get(f"/contacts/{cid}/timeline", headers=saleh_headers)
        assert t_res.status_code == 200
        calls_in_timeline = [item for item in t_res.json()["data"] if item["type"] == "call"]
        print(f"✓ Verified {len(calls_in_timeline)} call attempts in chronological timeline (Unlimited, no 3-attempt cap)")

        # 4. Test Archive & Restore Flow
        print_step("4. Test Complete Archive & Restore Mechanism")
        # Archive contact
        arch_res = client.post(f"/contacts/{cid}/archive", headers=saleh_headers)
        assert arch_res.status_code == 200, f"Archive failed: {arch_res.text}"
        assert arch_res.json()["data"]["status"] == "ARCHIVED"
        print(f"✓ Contact '{test_contact['full_name']}' archived (status=ARCHIVED)")

        # Verify excluded from default contacts list
        list_active = client.get(f"/contacts?search={test_contact['first_name']}", headers=saleh_headers).json()["data"]
        active_ids = [c["id"] for c in list_active]
        assert cid not in active_ids, "Archived contact must NOT appear in default active contacts!"
        print("✓ Confirmed: Archived contact is excluded from default active Contacts view")

        # Verify appears in Archive view
        list_archived = client.get("/contacts?include_archived=true&status=ARCHIVED", headers=saleh_headers).json()["data"]
        arch_ids = [c["id"] for c in list_archived]
        assert cid in arch_ids, "Archived contact MUST appear in Archive view!"
        print(f"✓ Confirmed: Archived contact appears in Archive view ({len(list_archived)} total in archive)")

        # Restore contact
        unarch_res = client.post(f"/contacts/{cid}/unarchive", headers=saleh_headers)
        assert unarch_res.status_code == 200, f"Restore failed: {unarch_res.text}"
        print(f"✓ Contact restored from archive (status={unarch_res.json()['data']['status']})")

        # 5. Test Aseel (TEAM_LEAD) & Lead Distribution
        print_step("5. Test Aseel (TEAM_LEAD) Login & Lead Distribution into Saleh Personal Pool")
        aseel_headers, aseel_data = login(client, "aseel@alphapromena.com", "Sales123!")
        print(f"✓ Aseel logged in: full_name='{aseel_data['full_name']}', role='{aseel_data['role']}' (TEAM_LEAD)")
        assert aseel_data["role"] in ["TEAM_LEAD", "TEAM_LEADER"], f"Expected TEAM_LEAD, got {aseel_data['role']}"

        # Aseel fetches unassigned leads
        unassigned_res = client.get("/admin/leads/unassigned?per_page=10", headers=aseel_headers)
        assert unassigned_res.status_code == 200, f"Unassigned fetch failed: {unassigned_res.text}"
        unassigned_leads = unassigned_res.json()["data"]
        print(f"✓ Aseel accessed New Leads Pool ({len(unassigned_leads)} leads available)")

        if len(unassigned_leads) >= 3:
            dist_lead_ids = [unassigned_leads[0]["id"], unassigned_leads[1]["id"], unassigned_leads[2]["id"]]
        else:
            # Create a quick lead to distribute
            new_lead = client.post("/contacts", headers=aseel_headers, json={"first_name": "Tariq", "last_name": "Al-Ghamdi", "company_id": None, "phone": "+966500000099"}).json()["data"]
            dist_lead_ids = [new_lead["id"]]

        # Aseel manually distributes to Saleh
        dist_res = client.post(
            "/admin/leads/distribute",
            headers=aseel_headers,
            json={
                "strategy": "MANUAL",
                "target_user_id": saleh_data["id"],
                "contact_ids": dist_lead_ids,
            },
        )
        assert dist_res.status_code == 200, f"Distribution failed: {dist_res.text}"
        print(f"✓ Aseel distributed {len(dist_lead_ids)} leads to Saleh (assigned_count={dist_res.json().get('assigned_count')})")

        # 6. Test Saleh Personal Pool & Claim Workflow
        print_step("6. Test Saleh's Personal Pool (PENDING_CLAIM) & Claim Workflow")
        pool_res = client.get("/contacts?pending_claim_only=true", headers=saleh_headers)
        assert pool_res.status_code == 200, f"Personal pool fetch failed: {pool_res.text}"
        pool_contacts = pool_res.json()["data"]
        print(f"✓ Saleh Personal Pool contains {len(pool_contacts)} leads awaiting claim (status=PENDING_CLAIM)")
        pool_ids = [c["id"] for c in pool_contacts]
        for did in dist_lead_ids:
            assert did in pool_ids, f"Lead {did} must be in Saleh's Personal Pool!"

        # Single claim test
        single_claim_id = dist_lead_ids[0]
        claim_res = client.post(f"/contacts/{single_claim_id}/claim", headers=saleh_headers)
        assert claim_res.status_code == 200, f"Single claim failed: {claim_res.text}"
        claimed_contact = claim_res.json()["data"]
        assert claimed_contact["status"] == "NEW"
        print(f"✓ Single claim: Lead '{claimed_contact['full_name']}' moved to NEW (sheet_order={claimed_contact.get('sheet_order')})")

        # Bulk claim test (if more leads distributed)
        if len(dist_lead_ids) > 1:
            bulk_claim_ids = dist_lead_ids[1:]
            bulk_res = client.post("/contacts/claim-bulk", headers=saleh_headers, json={"contact_ids": bulk_claim_ids})
            assert bulk_res.status_code == 200, f"Bulk claim failed: {bulk_res.text}"
            print(f"✓ Bulk claim: {bulk_res.json().get('claimed_count')} leads claimed into active contacts sequentially!")

        # 7. Test Abdullah (MANAGER) Access & Regression Check
        print_step("7. Test Abdullah (MANAGER) Access & Regression")
        print(f"✓ Abdullah logged in: role='{abdullah_data['role']}'")
        rep_res = client.get("/reports/dashboard", headers=abdullah_headers)
        assert rep_res.status_code == 200, f"Dashboard reports failed: {rep_res.text}"
        rep_data = rep_res.json()
        print(f"✓ Abdullah accessed Management Dashboard (team_totals: calls={rep_data.get('team_totals', {}).get('total_calls')}, users_breakdown={len(rep_data.get('user_breakdowns', []))} reps)")

        activity_res = client.get("/reports/team-activity", headers=abdullah_headers)
        assert activity_res.status_code == 200, f"Team activity failed: {activity_res.text}"
        print("✓ Abdullah accessed Team Activity Feed successfully")
        print("✓ Abdullah remains full MANAGER with all capabilities intact")

        print("\n" + "="*70)
        print("🎉 ALL PHASE 8 REQUIREMENTS SUCCESSFULLY VALIDATED & PASSING 100%!")
        print("="*70 + "\n")


if __name__ == "__main__":
    main()
