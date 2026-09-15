"""
Tests for operational metrics reconciliation and oversight table (req 1, 2).
Verifies that:
- Direct EmailActivity and WhatsAppActivity are counted.
- Call outcomes (e.g. EMAIL_REQUESTED, WHATSAPP_REQUESTED) are NOT double-counted as emails or whatsapp.
- total_activities = calls + emails + whatsapp.
- Date boundaries isolate correctly.
- user_performance_totals row reconciles with individual rows.
"""
from datetime import datetime, timezone, timedelta
import pytest


async def _login(client, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_operational_metrics_reconciliation(client, seed_test_users, db_session):
    """Verifies that operational performance metrics accurately count records and total reconciles."""
    from app.models.contact import Contact, ContactStatus
    from app.models.call import Call
    from app.models.activity import EmailActivity, WhatsAppActivity
    from app.models.task import Task, TaskStatus, TaskType

    token = await _login(client, "admin@test.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    admin = seed_test_users["admin"]
    sales_rep = seed_test_users["sales"]

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # Create contact for test
    contact = Contact(
        first_name="Operational",
        last_name="TestContact",
        phone="+966500001111",
        status=ContactStatus.NEW,
        owner_id=sales_rep.id,
    )
    db_session.add(contact)
    await db_session.flush()

    # 1. Add 2 calls for sales_rep today: 1 ANSWERED, 1 EMAIL_REQUESTED
    call1 = Call(
        contact_id=contact.id,
        user_id=sales_rep.id,
        outcome="ANSWERED",
        duration_seconds=120,
        called_at=now,
    )
    call2 = Call(
        contact_id=contact.id,
        user_id=sales_rep.id,
        outcome="EMAIL_REQUESTED",
        duration_seconds=45,
        called_at=now,
    )
    db_session.add_all([call1, call2])

    # 2. Add 1 EmailActivity today
    email_act = EmailActivity(
        contact_id=contact.id,
        user_id=sales_rep.id,
        subject="Product Catalog",
        direction="OUTBOUND",
        sent_at=now,
    )
    db_session.add(email_act)

    # 3. Add 1 WhatsAppActivity today
    wa_act = WhatsAppActivity(
        contact_id=contact.id,
        user_id=sales_rep.id,
        direction="OUTBOUND",
        message_preview="Hello, following up on our call",
        sent_at=now,
    )
    db_session.add(wa_act)

    # 4. Add 1 Task (EMAIL, COMPLETED) today
    task_email = Task(
        title="Send catalog follow-up",
        contact_id=contact.id,
        assigned_to=sales_rep.id,
        type=TaskType.EMAIL,
        status=TaskStatus.COMPLETED,
        completed_at=now,
    )
    db_session.add(task_email)

    # 5. Add 1 Call from 10 days ago (should be excluded by date range)
    past_call = Call(
        contact_id=contact.id,
        user_id=sales_rep.id,
        outcome="ANSWERED",
        duration_seconds=60,
        called_at=now - timedelta(days=10),
    )
    db_session.add(past_call)
    await db_session.flush()

    # Query dashboard for today
    r = await client.get(
        f"/api/v1/reports/dashboard?date_from={today_str}&date_to={today_str}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert "user_performance" in data
    assert "user_performance_totals" in data

    # Find sales_rep row
    rep_row = next((u for u in data["user_performance"] if u["user_id"] == str(sales_rep.id)), None)
    assert rep_row is not None, f"sales_rep not found in performance table: {data['user_performance']}"

    # Verify counts:
    # calls = 2 (today's calls, past call excluded)
    assert rep_row["calls"] == 2, f"Expected 2 calls, got {rep_row['calls']}"
    assert rep_row["emails"] == 2, f"Expected 2 emails, got {rep_row['emails']}"
    assert rep_row["whatsapp"] == 1, f"Expected 1 whatsapp, got {rep_row['whatsapp']}"
    assert rep_row["total_activities"] == 5, f"Expected 5 total activities, got {rep_row['total_activities']}"

    # Check totals row reconciliation:
    totals = data["user_performance_totals"]
    sum_calls = sum(u["calls"] for u in data["user_performance"])
    sum_emails = sum(u["emails"] for u in data["user_performance"])
    sum_whatsapp = sum(u["whatsapp"] for u in data["user_performance"])
    sum_total = sum(u["total_activities"] for u in data["user_performance"])

    assert totals["calls"] == sum_calls
    assert totals["emails"] == sum_emails
    assert totals["whatsapp"] == sum_whatsapp
    assert totals["total_activities"] == sum_total
