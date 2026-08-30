import asyncio
import httpx
import sys

BASE_URL = "http://localhost:8000/api/v1"

ACCOUNTS = [
    ("saleh@alphapromena.com", "Sales123!", "USER"),
    ("hasan@alphapromena.com", "Sales123!", "USER"),
    ("amin@alphapromena.com", "Sales123!", "USER"),
    ("ghaida@alphapromena.com", "Sales123!", "USER"),
    ("qusai@alphapromena.com", "Sales123!", "TEAM_LEAD"),
    ("abdallah@alphapromena.com", "Manager123!", "MANAGER"),
]

async def verify_all():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        tokens = {}
        print("=== 1. Testing Login for all 6 official accounts ===")
        for email, pwd, expected_role in ACCOUNTS:
            res = await client.post("/auth/login", json={"email": email, "password": pwd})
            assert res.status_code == 200, f"Login failed for {email}: {res.text}"
            token = res.json()["access_token"]
            tokens[email] = token
            
            me_res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me_res.status_code == 200
            user_data = me_res.json()
            assert user_data["role"] == expected_role, f"Role mismatch for {email}: got {user_data['role']}, expected {expected_role}"
            print(f"  [OK] {email} ({user_data['role']}) login OK. ID: {user_data['id']}")

        print("\n=== 2. Testing Scoped Dashboard for Saleh (Sales Rep) ===")
        saleh_token = tokens["saleh@alphapromena.com"]
        res = await client.get("/reports/dashboard?date_from=2026-07-01", headers={"Authorization": f"Bearer {saleh_token}"})
        assert res.status_code == 200
        saleh_dash = res.json()["data"]
        kpis = saleh_dash["kpis"]
        print(f"  [OK] Saleh calls: {kpis['total_calls']}, contacts: {kpis['total_contacts']}")
        assert kpis['total_calls'] == 2698, f"Saleh calls mismatch: {kpis['total_calls']}"
        assert kpis['total_contacts'] == 999, f"Saleh contacts mismatch: {kpis['total_contacts']}"

        print("\n=== 3. Testing Scoped Dashboard for Abdallah (Manager) ===")
        abdallah_token = tokens["abdallah@alphapromena.com"]
        res = await client.get("/reports/dashboard?date_from=2026-07-01", headers={"Authorization": f"Bearer {abdallah_token}"})
        assert res.status_code == 200
        mgr_dash = res.json()["data"]
        kpis = mgr_dash["kpis"]
        print(f"  [OK] Abdallah (Company Total) calls: {kpis['total_calls']}, contacts: {kpis['total_contacts']}")
        assert kpis['total_calls'] == 9626
        assert kpis['total_contacts'] == 3965

        # Check Operational Performance Table rows: only 4 sales reps, first names only
        user_breakdown = mgr_dash.get("user_breakdown") or mgr_dash.get("user_performance", [])
        rep_names = [u["user_name"] for u in user_breakdown]
        print(f"  [OK] Operational Performance Reps: {rep_names}")
        assert set(rep_names) == {"Saleh", "Hasan", "Amin", "Ghaida"}, f"Unexpected reps in performance table: {rep_names}"

        print("\n=== 4. Testing Contacts Continuous Endpoint ===")
        res = await client.get("/contacts?per_page=100&page=1", headers={"Authorization": f"Bearer {abdallah_token}"})
        assert res.status_code == 200
        contacts_data = res.json()
        meta = contacts_data["meta"]
        data = contacts_data["data"]
        print(f"  [OK] Total contacts: {meta['total']}, fetched in batch: {len(data)}")
        assert meta['total'] == 3965
        assert len(data) == 100
        first_c = data[0]
        assert "attempt_1" in first_c
        assert "attempt_2" in first_c
        assert "attempt_3" in first_c
        print(f"  [OK] Sample contact attempt history: 1st='{first_c['attempt_1']}', 2nd='{first_c['attempt_2']}', 3rd='{first_c['attempt_3']}'")

        print("\n=== 5. Testing Follow-ups List ===")
        res = await client.get("/follow-ups", headers={"Authorization": f"Bearer {abdallah_token}"})
        assert res.status_code == 200
        followups = res.json()["data"]
        print(f"  [OK] Follow-ups count: {len(followups)}")
        assert len(followups) > 0

        print("\n=== 6. Testing Demos List ===")
        res = await client.get("/demos", headers={"Authorization": f"Bearer {abdallah_token}"})
        assert res.status_code == 200
        demos_res = res.json()
        demos_total = demos_res.get("meta", {}).get("total", len(demos_res.get("data", [])))
        print(f"  [OK] Demos total count: {demos_total}")
        assert demos_total == 117

        print("\n=== ALL INTEGRATION VERIFICATIONS PASSED 100%! ===")

if __name__ == "__main__":
    asyncio.run(verify_all())
