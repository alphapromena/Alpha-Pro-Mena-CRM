"""
Tests for follow-up creation without a CRM contact (req 9).
"""
from datetime import datetime, timezone, timedelta
import pytest


async def _login(client, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_follow_up_without_contact(client, seed_test_users, db_session):
    """A follow-up can be created with only company_name_snapshot — no contact_id required."""
    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/api/v1/follow-ups", headers=headers, json={
        "company_name_snapshot": "Unknown Company LLC",
        "meeting_with": "Ahmed Al-Rashid",
        "type": "GENERAL",
        "due_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
        "notes": "Called from cold list, no CRM record yet",
    })
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["contact_id"] is None
    assert data["company_name_snapshot"] == "Unknown Company LLC"
    assert data["meeting_with"] == "Ahmed Al-Rashid"


@pytest.mark.asyncio
async def test_create_follow_up_with_contact_and_snapshot(client, seed_test_users, db_session):
    """A follow-up created with a contact also stores company_name_snapshot."""
    from app.models.contact import Contact, ContactStatus

    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    admin = seed_test_users["admin"]

    contact = Contact(
        first_name="Layla",
        last_name="Hassan",
        phone="+971501112233",
        status=ContactStatus.NEW,
        owner_id=admin.id,
    )
    db_session.add(contact)
    await db_session.flush()

    r = await client.post("/api/v1/follow-ups", headers=headers, json={
        "contact_id": str(contact.id),
        "company_name_snapshot": "Acme Corp",
        "meeting_with": "Layla Hassan",
        "type": "CALL",
        "due_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    })
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["contact_id"] == str(contact.id)
    assert data["company_name_snapshot"] == "Acme Corp"
    assert data["meeting_with"] == "Layla Hassan"


@pytest.mark.asyncio
async def test_follow_up_with_undated_entry(client, seed_test_users, db_session):
    """A follow-up without a due_at (historical/undated) should be accepted."""
    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/api/v1/follow-ups", headers=headers, json={
        "company_name_snapshot": "Pending Corp",
        "type": "GENERAL",
        # no due_at
    })
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["due_at"] is None
    assert data["company_name_snapshot"] == "Pending Corp"


@pytest.mark.asyncio
async def test_update_follow_up_fields(client, seed_test_users, db_session):
    """Updating company_name_snapshot and next_step via PATCH."""
    from app.models.follow_up import FollowUp

    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    admin = seed_test_users["admin"]

    fu = FollowUp(
        user_id=admin.id,
        type="GENERAL",
        status="PENDING",
        due_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db_session.add(fu)
    await db_session.flush()

    r = await client.patch(f"/api/v1/follow-ups/{fu.id}", headers=headers, json={
        "company_name_snapshot": "Updated Corp",
        "next_step": "Schedule a demo next Monday",
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["company_name_snapshot"] == "Updated Corp"
    assert data["next_step"] == "Schedule a demo next Monday"
