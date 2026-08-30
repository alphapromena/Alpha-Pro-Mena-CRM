import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

async def verify_all_logins():
    accounts_to_test = [
        ("saleh@alphapromena.com", "Sales123!"),
        ("qusai@alphapromena.com", "Sales123!"),
        ("hassan@alphapromena.com", "Sales123!"),
        ("amin@alphapromena.com", "Sales123!"),
        ("ghaida@alphapromena.com", "Sales123!"),
        ("manager@alphapromena.com", "Manager123!"),
        ("admin@alphapromena.com", "Admin123!"),
        ("saleh@alphapro.com", "Sales123!"),
        ("qusai@alphapro.com", "Sales123!"),
    ]

    print("\n" + "=" * 70)
    print("ALL ACCOUNTS END-TO-END VERIFICATION")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for email, password in accounts_to_test:
            resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                headers = {"Authorization": f"Bearer {token}"}
                me_resp = await client.get("/api/v1/auth/me", headers=headers)
                me_data = me_resp.json()
                print(f"  [OK 200] {email:<28} -> Role: {me_data['role']:<10} User: {me_data['full_name']}")
            else:
                print(f"  [ERR {resp.status_code}] {email:<28} -> {resp.text}")

    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(verify_all_logins())
