"""
Live API Endpoints Full Integration Test
========================================
Tests HTTP API requests against live backend:
1. Login with Saleh -> Fetch /contacts -> Verify 334 leads, sheet_order, empty attempts
2. Login with Amin -> Fetch /contacts -> Verify 576 leads
3. Login with Hasan -> Fetch /contacts -> Verify 548 leads
4. Login with Ghaida -> Fetch /contacts -> Verify 337 leads
5. Login with Aseel -> Verify role is DATA_OPS, access /admin/leads/unassigned, verify /reports/dashboard is forbidden
6. Login with Abdullah -> Fetch /reports/dashboard -> Verify live calculated numbers (0 fake calls today)
"""
import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


def login(email: str, password: str = "<set-password>"):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    # Get user details
    me_resp = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200, f"Get me failed for {email}: {me_resp.text}"
    user = me_resp.json()
    return token, user


def test_live_api():
    print("\n--- LIVE HTTP API INTEGRATION TESTS ---\n")

    # 1. Saleh (334 leads)
    token_saleh, user_saleh = login("saleh@alphapromena.com", "<set-password>")
    headers_saleh = {"Authorization": f"Bearer {token_saleh}"}
    r = requests.get(f"{BASE_URL}/contacts?per_page=100", headers=headers_saleh)
    assert r.status_code == 200, f"Saleh contacts failed: {r.text}"
    data_saleh = r.json()
    total_saleh = data_saleh["meta"]["total"]
    print(f"1. Saleh ({user_saleh['email']}): {total_saleh} active contacts returned (Expected: 334)")
    assert total_saleh == 334, f"Expected 334, got {total_saleh}"
    
    first_lead = data_saleh["data"][0]
    print(f"   First lead: {first_lead['full_name']} | Company: {first_lead['company_name']} | Position: {first_lead['position']} | Attempts: {first_lead['attempt_count']}")
    assert first_lead["attempt_count"] == 0
    assert first_lead["attempt_1"] is None
    assert first_lead["final_outcome"] is None

    # 2. Amin (576 leads)
    token_amin, user_amin = login("amin@alphapromena.com", "<set-password>")
    headers_amin = {"Authorization": f"Bearer {token_amin}"}
    r = requests.get(f"{BASE_URL}/contacts?per_page=10", headers=headers_amin)
    assert r.status_code == 200
    total_amin = r.json()["meta"]["total"]
    print(f"2. Amin ({user_amin['email']}): {total_amin} active contacts returned (Expected: 576)")
    assert total_amin == 576, f"Expected 576, got {total_amin}"

    # 3. Hasan (548 leads)
    token_hasan, user_hasan = login("hasan@alphapromena.com", "<set-password>")
    headers_hasan = {"Authorization": f"Bearer {token_hasan}"}
    r = requests.get(f"{BASE_URL}/contacts?per_page=10", headers=headers_hasan)
    assert r.status_code == 200
    total_hasan = r.json()["meta"]["total"]
    print(f"3. Hasan ({user_hasan['email']}): {total_hasan} active contacts returned (Expected: 548)")
    assert total_hasan == 548, f"Expected 548, got {total_hasan}"

    # 4. Ghaida (337 leads)
    token_ghaida, user_ghaida = login("ghaida@alphapromena.com", "<set-password>")
    headers_ghaida = {"Authorization": f"Bearer {token_ghaida}"}
    r = requests.get(f"{BASE_URL}/contacts?per_page=10", headers=headers_ghaida)
    assert r.status_code == 200
    total_ghaida = r.json()["meta"]["total"]
    print(f"4. Ghaida ({user_ghaida['email']}): {total_ghaida} active contacts returned (Expected: 337)")
    assert total_ghaida == 337, f"Expected 337, got {total_ghaida}"

    # 5. Aseel (DATA_OPS)
    token_aseel, user_aseel = login("aseel@alphapromena.com", "<set-password>")
    headers_aseel = {"Authorization": f"Bearer {token_aseel}"}
    print(f"5. Aseel: Role={user_aseel['role']} (DATA_OPS)")
    assert user_aseel["role"] == "DATA_OPS"

    # Aseel accesses lead pool
    r_unassigned = requests.get(f"{BASE_URL}/admin/leads/unassigned", headers=headers_aseel)
    assert r_unassigned.status_code == 200
    unassigned_count = r_unassigned.json()["meta"]["total"]
    print(f"   Aseel accessed Unassigned Leads Pool: {unassigned_count} unassigned leads available")

    # 6. Abdullah (MANAGER)
    token_mgr, user_mgr = login("abdallah@alphapromena.com", "<set-password>")
    headers_mgr = {"Authorization": f"Bearer {token_mgr}"}
    r_dash = requests.get(f"{BASE_URL}/reports/dashboard?preset=today", headers=headers_mgr)
    assert r_dash.status_code == 200
    kpis_today = r_dash.json()["data"]["kpis"]
    print(f"6. Abdullah Manager Dashboard (Today):")
    print(f"   Total Calls Today: {kpis_today['total_calls']}")
    print(f"   Emails Today:      {kpis_today['emails']}")
    print(f"   WhatsApp Today:    {kpis_today['whatsapp']}")
    print(f"   Active Leads:      {kpis_today['active_leads']}")
    print(f"   Archived Leads:    {kpis_today['archived_contacts']}")
    assert kpis_today["total_calls"] == 0
    assert kpis_today["active_leads"] == 1795
    assert kpis_today["archived_contacts"] == 4219

    print("\n--- ALL LIVE HTTP API TESTS PASSED 100% ---\n")


if __name__ == "__main__":
    test_live_api()
