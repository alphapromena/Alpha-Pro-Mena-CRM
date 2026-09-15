"""
Tests for Demo → Follow-up conversion (req 9, req 10).
"""
from datetime import datetime, timezone, timedelta
import pytest


async def _login(client, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_convert_demo_to_follow_up(client, seed_test_users, db_session):
    """Converting a Demo creates a FollowUp prefilled with Demo data and marks the demo."""
    from app.models.contact import Contact, ContactStatus
    from app.models.demo import Demo, DemoStage, DemoStatus, DemoReportStatus
    from app.models.follow_up import FollowUp

    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    admin = seed_test_users["admin"]

    contact = Contact(
        first_name="Sara",
        last_name="Khalil",
        phone="+971501234567",
        status=ContactStatus.NEW,
        owner_id=admin.id,
    )
    db_session.add(contact)
    await db_session.flush()

    demo = Demo(
        contact_id=contact.id,
        owner_id=admin.id,
        stage=DemoStage.COMPLETED,
        status=DemoStatus.INTERESTED_NEXT_STEP,
        company_name_snapshot="Khalil Enterprises",
        meeting_with="Sara Khalil",
        next_step="Follow up about pricing",
        next_step_due_date=datetime.now(timezone.utc) + timedelta(days=5),
        report_status=DemoReportStatus.REPORT_COMPLETE,
        created_by_id=admin.id,
    )
    db_session.add(demo)
    await db_session.flush()

    r = await client.post(
        f"/api/v1/demos/{demo.id}/convert-to-follow-up",
        headers=headers,
        json={},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["created"] is True
    assert data["company_name_snapshot"] == "Khalil Enterprises"
    assert data["meeting_with"] == "Sara Khalil"
    assert data["follow_up_id"] is not None

    # Verify demo was marked as converted
    await db_session.refresh(demo)
    assert demo.converted_to_follow_up_id is not None
    assert demo.converted_to_follow_up_at is not None


@pytest.mark.asyncio
async def test_convert_demo_to_follow_up_idempotent(client, seed_test_users, db_session):
    """Converting the same Demo twice returns the existing FollowUp instead of creating a new one."""
    from app.models.contact import Contact, ContactStatus
    from app.models.demo import Demo, DemoStage, DemoStatus, DemoReportStatus
    from app.models.follow_up import FollowUp

    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    admin = seed_test_users["admin"]

    contact = Contact(
        first_name="Hassan",
        last_name="Ali",
        phone="+97150999888",
        status=ContactStatus.NEW,
        owner_id=admin.id,
    )
    db_session.add(contact)
    await db_session.flush()

    # Create a follow-up for the demo already
    existing_fu = FollowUp(
        contact_id=contact.id,
        user_id=admin.id,
        type="DEMO",
        status="PENDING",
        due_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db_session.add(existing_fu)
    await db_session.flush()

    demo = Demo(
        contact_id=contact.id,
        owner_id=admin.id,
        stage=DemoStage.COMPLETED,
        status=DemoStatus.INTERESTED_NEXT_STEP,
        report_status=DemoReportStatus.REPORT_COMPLETE,
        created_by_id=admin.id,
        converted_to_follow_up_id=existing_fu.id,
        converted_to_follow_up_at=datetime.now(timezone.utc),
    )
    db_session.add(demo)
    await db_session.flush()

    r = await client.post(
        f"/api/v1/demos/{demo.id}/convert-to-follow-up",
        headers=headers,
        json={},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    # Should return the existing follow-up, not create a new one
    assert data["created"] is False
    assert data["follow_up_id"] == str(existing_fu.id)


@pytest.mark.asyncio
async def test_convert_demo_prefills_next_step_due_date(client, seed_test_users, db_session):
    """The converted follow-up's due_at is prefilled from demo.next_step_due_date."""
    from app.models.contact import Contact, ContactStatus
    from app.models.demo import Demo, DemoStage, DemoStatus, DemoReportStatus

    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    admin = seed_test_users["admin"]

    contact = Contact(
        first_name="Fatima",
        last_name="Nour",
        phone="+97150888777",
        status=ContactStatus.NEW,
        owner_id=admin.id,
    )
    db_session.add(contact)
    await db_session.flush()

    due_date = datetime.now(timezone.utc) + timedelta(days=7)
    demo = Demo(
        contact_id=contact.id,
        owner_id=admin.id,
        stage=DemoStage.COMPLETED,
        status=DemoStatus.INTERESTED_NEXT_STEP,
        next_step_due_date=due_date,
        report_status=DemoReportStatus.REPORT_COMPLETE,
        created_by_id=admin.id,
    )
    db_session.add(demo)
    await db_session.flush()

    r = await client.post(
        f"/api/v1/demos/{demo.id}/convert-to-follow-up",
        headers=headers,
        json={},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["due_at"] is not None
    # Due date should match demo's next_step_due_date (within same second)
    due_parsed = datetime.fromisoformat(data["due_at"])
    assert abs((due_parsed - due_date).total_seconds()) < 2
