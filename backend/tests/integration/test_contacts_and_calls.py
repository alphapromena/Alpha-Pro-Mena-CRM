"""
Integration tests for Contacts CRUD, Call Logging, and DNC Enforcement.
"""
import pytest
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_create_and_fetch_contact(client, seed_test_users):
    sales_user = seed_test_users["sales"]
    token = create_access_token(sales_user.id, sales_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Contact
    create_resp = await client.post(
        "/api/v1/contacts",
        headers=headers,
        json={
            "first_name": "Tariq",
            "last_name": "Al-Amri",
            "email": "tariq.amri@testcorp.sa",
            "phone": "+966509988776",
            "country": "Saudi Arabia",
            "industry": "Fintech",
            "position": "CEO",
        },
    )
    assert create_resp.status_code == 201
    contact_data = create_resp.json()["data"]
    contact_id = contact_data["id"]
    assert contact_data["first_name"] == "Tariq"
    assert contact_data["status"] == "NEW"

    # 2. Log a Call
    call_resp = await client.post(
        "/api/v1/calls",
        headers=headers,
        json={
            "contact_id": contact_id,
            "outcome": "INTERESTED",
            "notes": "Discussed regional expansion.",
            "duration_seconds": 180,
        },
    )
    assert call_resp.status_code == 201
    assert call_resp.json()["data"]["outcome"] == "INTERESTED"

    # 3. Set DNC
    dnc_resp = await client.post(
        f"/api/v1/contacts/{contact_id}/dnc",
        headers=headers,
    )
    assert dnc_resp.status_code == 200
    assert dnc_resp.json()["data"]["is_dnc"] is True

    # 4. Attempt call on DNC contact -> should be rejected with 409
    call_dnc_resp = await client.post(
        "/api/v1/calls",
        headers=headers,
        json={
            "contact_id": contact_id,
            "outcome": "NO_ANSWER",
        },
    )
    assert call_dnc_resp.status_code == 409
    assert call_dnc_resp.json()["error"]["code"] == "DO_NOT_CONTACT"
