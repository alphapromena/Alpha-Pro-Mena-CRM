"""
Comprehensive integration tests for CRM Security, Demo History, Contact Editing,
and Connected Dashboard functionality.
"""
import uuid
import io
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import (
    create_access_token,
    hash_password,
    normalize_email,
    generate_secure_token,
    hash_token,
)
from app.models.user import User, UserRole
from app.models.contact import Contact, ContactStatus
from app.models.company import Company
from app.models.demo import Demo, DemoStatus, DemoReportStatus
from app.models.audit import AuditLog


async def _create_test_user(
    db: AsyncSession,
    role: UserRole = UserRole.SALES_USER,
    email_prefix: str = "agent",
    must_change_password: bool = False,
    email_verified: bool = True,
    password: str = "TestPass123!",
) -> tuple[User, str]:
    email = f"{email_prefix}_{uuid.uuid4().hex[:6]}@alphapromena.com"
    user = User(
        email=email,
        normalized_email=normalize_email(email),
        first_name=email_prefix.capitalize(),
        last_name="Tester",
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        must_change_password=must_change_password,
        email_verified=email_verified,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(user_id=user.id, role=user.role)
    return user, token


async def _create_company_and_contact(
    db: AsyncSession, owner_id: uuid.UUID
) -> tuple[Company, Contact]:
    company = Company(
        name=f"Enterprise {uuid.uuid4().hex[:4]}",
        domain=f"enterprise-{uuid.uuid4().hex[:4]}.com",
        industry="Technology",
        country="United Arab Emirates",
    )
    db.add(company)
    await db.flush()

    c_email = f"layla_{uuid.uuid4().hex[:6]}@company.ae"
    contact = Contact(
        first_name="Layla",
        last_name="Mansour",
        email=c_email,
        normalized_email=normalize_email(c_email),
        phone="+971501234567",
        company_id=company.id,
        owner_id=owner_id,
        status=ContactStatus.NEW,
    )
    db.add(contact)
    await db.flush()
    return company, contact


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTHENTICATION & TEAM SECURITY
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_first_login_forced_password_change(client: AsyncClient, db_session: AsyncSession):
    """Users with must_change_password=True must activate their password on first login."""
    user, _ = await _create_test_user(
        db_session,
        email_prefix="activation",
        must_change_password=True,
        password="TempPassword123!",
    )

    # 1. Login should notify must_change_password is True
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "TempPassword123!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["must_change_password"] is True
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Reject weak new password (fails strength validation)
    weak_resp = await client.post(
        "/api/v1/auth/activate-password",
        headers=headers,
        json={"new_password": "weak"},
    )
    assert weak_resp.status_code == 422

    # 3. Accept strong new personal password
    activate_resp = await client.post(
        "/api/v1/auth/activate-password",
        headers=headers,
        json={"new_password": "PersonalStrongPass2026!"},
    )
    assert activate_resp.status_code == 200

    # 4. Verify /auth/me reflects must_change_password=False
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["must_change_password"] is False

    # 5. Old password no longer works
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "TempPassword123!"},
    )
    assert old_login.status_code == 401

    # 6. New password works
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "PersonalStrongPass2026!"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is False


@pytest.mark.asyncio
async def test_email_verification_token_flow_and_cooldown(
    client: AsyncClient, db_session: AsyncSession
):
    """Test one-time email verification token, expiry handling, and resend cooldown."""
    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)

    u_email = f"verify_{uuid.uuid4().hex[:6]}@alphapromena.com"
    user = User(
        email=u_email,
        normalized_email=normalize_email(u_email),
        first_name="Verify",
        last_name="User",
        password_hash=hash_password("Pass12345!"),
        role=UserRole.SALES_USER,
        is_active=True,
        email_verified=False,
        verification_token_hash=token_hash,
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(user)
    await db_session.flush()

    # 1. Invalid verification token fails (400)
    invalid_resp = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": "non_existent_token"},
    )
    assert invalid_resp.status_code == 400

    # 2. Resend verification token for unverified user
    resend_resp = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": user.email},
    )
    assert resend_resp.status_code == 200

    # 3. Immediate second resend is suppressed silently, not answered with 429.
    #    A distinct status here would confirm the address is registered, since an
    #    unknown address always receives the same neutral 200.
    cooldown_resp = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": user.email},
    )
    assert cooldown_resp.status_code == 200
    assert cooldown_resp.json()["message"] == resend_resp.json()["message"]

    # 4. Valid verification token succeeds (200)
    dev_mail_resp = await client.get(f"/api/v1/auth/dev-mail?email={user.email}")
    assert dev_mail_resp.status_code == 200
    mail_entries = dev_mail_resp.json()["messages"]
    latest_token = mail_entries[0]["token"]

    valid_resp = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": latest_token},
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json()["email_verified"] is True

    # 5. Token cannot be reused (one-time use)
    reuse_resp = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": latest_token},
    )
    assert reuse_resp.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient, db_session: AsyncSession):
    """Verify forgot-password token creation and reset-password execution."""
    user, _ = await _create_test_user(db_session, email_prefix="reset", password="OldPassword123!")

    # 1. Request password reset (anti-enumeration returns 200 even for non-existent emails)
    req_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
    )
    assert req_resp.status_code == 200

    # Inspect the user to fetch the token from dev mailbox or DB
    await db_session.refresh(user)
    assert user.password_reset_token_hash is not None

    # Dev mail endpoint allows verifying local mock mailbox
    dev_mail_resp = await client.get(f"/api/v1/auth/dev-mail?email={user.email}")
    assert dev_mail_resp.status_code == 200
    mail_entries = dev_mail_resp.json()["messages"]
    assert len(mail_entries) > 0
    raw_token = mail_entries[0]["token"]

    # 2. Reset password with token
    reset_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewResetPassword2026!"},
    )
    assert reset_resp.status_code == 200

    # 3. Verify user can log in with new password
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "NewResetPassword2026!"},
    )
    assert login_resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONTACT EDITING & GRANULAR AUDIT TRAIL
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_contact_edit_and_audit_diff(client: AsyncClient, db_session: AsyncSession):
    """Test updating contact profile (e.g. correcting wrong email) and audit recording."""
    user, token = await _create_test_user(db_session, role=UserRole.ADMIN, email_prefix="contactadmin")
    company, contact = await _create_company_and_contact(db_session, owner_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    old_email = contact.email
    corrected_email = f"corrected_{uuid.uuid4().hex[:4]}@company.ae"

    # 1. Update contact fields
    update_payload = {
        "first_name": "Layla-Jane",
        "email": corrected_email,
        "phone": "+971509998877",
        "job_title": "Chief Executive Officer",
        "notes": "Corrected misspelled email and updated executive role.",
    }

    resp = await client.patch(
        f"/api/v1/contacts/{contact.id}",
        headers=headers,
        json=update_payload,
    )
    assert resp.status_code == 200, f"Failed updating contact: {resp.text}"
    updated_data = resp.json()["data"]
    assert updated_data["first_name"] == "Layla-Jane"
    assert updated_data["email"] == corrected_email
    assert updated_data["job_title"] == "Chief Executive Officer"
    assert updated_data["position"] == "Chief Executive Officer"

    # 2. Verify Audit Log was recorded in DB
    audit_stmt = select(AuditLog).where(
        AuditLog.entity_type == "contact",
        AuditLog.entity_id == contact.id,
    )
    audit_res = await db_session.execute(audit_stmt)
    audit_entries = audit_res.scalars().all()
    assert len(audit_entries) >= 1

    latest_audit = audit_entries[-1]
    assert latest_audit.old_value is not None
    assert latest_audit.new_value is not None
    assert latest_audit.old_value.get("email") == old_email
    assert latest_audit.new_value.get("email") == corrected_email

    # 3. Verify Contact Timeline endpoint returns audit logs with diffs
    timeline_resp = await client.get(
        f"/api/v1/contacts/{contact.id}/timeline",
        headers=headers,
    )
    assert timeline_resp.status_code == 200
    timeline_items = timeline_resp.json()["data"]
    audit_timeline_items = [item for item in timeline_items if item["type"] == "audit"]
    assert len(audit_timeline_items) > 0
    assert "field_diffs" in audit_timeline_items[0]["audit"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. MANDATORY DEMO SUMMARIES & CONDITIONAL REPORT VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_mandatory_summary_and_status_rules(
    client: AsyncClient, db_session: AsyncSession
):
    """Every demo must require a summary and follow conditional status rules."""
    user, token = await _create_test_user(db_session, role=UserRole.SALES_USER, email_prefix="demorep")
    company, contact = await _create_company_and_contact(db_session, owner_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Missing or empty summary must be rejected (400 / 422)
    no_summary_resp = await client.post(
        "/api/v1/demos",
        headers=headers,
        json={
            "contact_id": str(contact.id),
            "company_id": str(company.id),
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "status": "PENDING",
            "summary": "   ",  # whitespace only
            "next_step": "Send product overview",
        },
    )
    assert no_summary_resp.status_code in (400, 422)

    # 2. Status 'INTERESTED' requires next_step
    interested_no_next_resp = await client.post(
        "/api/v1/demos",
        headers=headers,
        json={
            "contact_id": str(contact.id),
            "company_id": str(company.id),
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "status": "INTERESTED",
            "summary": "Demonstrated AI call tracking.",
            "next_step": "",  # missing
        },
    )
    assert interested_no_next_resp.status_code in (400, 422)

    # 3. Status 'POSTPONED' requires reason
    postponed_no_reason_resp = await client.post(
        "/api/v1/demos",
        headers=headers,
        json={
            "contact_id": str(contact.id),
            "company_id": str(company.id),
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "status": "POSTPONED",
            "summary": "Client requested to reschedule after Q3 budget review.",
            "reason": "",  # missing
        },
    )
    assert postponed_no_reason_resp.status_code in (400, 422)

    # 4. Status 'NOT_INTERESTED' requires reason
    not_interested_no_reason_resp = await client.post(
        "/api/v1/demos",
        headers=headers,
        json={
            "contact_id": str(contact.id),
            "company_id": str(company.id),
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "status": "NOT_INTERESTED",
            "summary": "Client opted for internal tool.",
            "reason": None,
        },
    )
    assert not_interested_no_reason_resp.status_code in (400, 422)

    # 5. Valid demo creation succeeds
    valid_resp = await client.post(
        "/api/v1/demos",
        headers=headers,
        json={
            "contact_id": str(contact.id),
            "company_id": str(company.id),
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "status": "INTERESTED",
            "summary": "Comprehensive walkthrough of CRM dashboard and lead routing.",
            "next_step": "Submit enterprise proposal and pricing sheet.",
            "next_step_due_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "presenter": "Saleh",
            "attendees": "Layla Mansour, Tariq Al-Amri",
        },
    )
    assert valid_resp.status_code == 201
    created_demo = valid_resp.json()["data"]
    assert created_demo["report_status"] == "REPORT_COMPLETE"
    assert created_demo["status"] == "INTERESTED_NEXT_STEP"


@pytest.mark.asyncio
async def test_complete_demo_report_endpoint(client: AsyncClient, db_session: AsyncSession):
    """Test completing a report for an existing demo via /demos/{id}/report."""
    user, token = await _create_test_user(db_session, role=UserRole.ADMIN, email_prefix="reportadmin")
    company, contact = await _create_company_and_contact(db_session, owner_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Create demo with NEEDS_REPORT
    demo = Demo(
        company_id=company.id,
        contact_id=contact.id,
        owner_id=user.id,
        scheduled_at=datetime.now(timezone.utc),
        status=DemoStatus.PENDING,
        summary="Brief call",
        report_status=DemoReportStatus.NEEDS_REPORT,
    )
    db_session.add(demo)
    await db_session.flush()

    # Complete the report
    report_resp = await client.patch(
        f"/api/v1/demos/{demo.id}/report",
        headers=headers,
        json={
            "summary": "Completed comprehensive platform demonstration with engineering heads.",
            "status": "INTERESTED_NEXT_STEP",
            "result": "Positive reception; procurement process initiated.",
            "next_step": "Draft master service agreement",
            "presenter": "Amin",
            "attendees": "VP Technology, Head of Sales",
        },
    )
    assert report_resp.status_code == 200
    report_data = report_resp.json()["data"]
    assert report_data["report_status"] == "REPORT_COMPLETE"
    assert report_data["status"] == "INTERESTED_NEXT_STEP"
    assert report_data["presenter"] == "Amin"


# ─────────────────────────────────────────────────────────────────────────────
# 4. STATUS FILTERS & COUNTS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_status_filters_and_counts(client: AsyncClient, db_session: AsyncSession):
    """Test status filter tabs (Interested, Pending, Postponed, etc.) and /demos/counts."""
    user, token = await _create_test_user(db_session, role=UserRole.ADMIN, email_prefix="filteradmin")
    company, contact = await _create_company_and_contact(db_session, owner_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Create one of each status
    statuses = [
        (DemoStatus.INTERESTED_NEXT_STEP, "Interested summary", "Send contract", None),
        (DemoStatus.PENDING, "Pending summary", "Awaiting follow-up confirmation", None),
        (DemoStatus.POSTPONED, "Postponed summary", None, "Client traveling abroad"),
        (DemoStatus.NOT_INTERESTED, "Not interested summary", None, "Budget cut"),
        (DemoStatus.CANCELLED, "Cancelled summary", None, "Meeting conflict"),
    ]

    for status_val, summary, next_step, reason in statuses:
        d = Demo(
            company_id=company.id,
            contact_id=contact.id,
            owner_id=user.id,
            scheduled_at=datetime.now(timezone.utc),
            status=status_val,
            summary=summary,
            next_step=next_step,
            reason=reason,
            report_status=DemoReportStatus.REPORT_COMPLETE,
        )
        db_session.add(d)
    await db_session.flush()

    # 1. Fetch counts
    counts_resp = await client.get("/api/v1/demos/counts", headers=headers)
    assert counts_resp.status_code == 200
    counts = counts_resp.json()["data"]
    assert counts["all"] >= 5
    assert counts["interested"] >= 1
    assert counts["pending"] >= 1
    assert counts["postponed"] >= 1
    assert counts["not_interested"] >= 1
    assert counts["cancelled"] >= 1

    # 2. Filter by status: INTERESTED_NEXT_STEP
    interested_resp = await client.get("/api/v1/demos?status=INTERESTED_NEXT_STEP", headers=headers)
    assert interested_resp.status_code == 200
    items = interested_resp.json()["data"]
    for item in items:
        assert item["status"] == "INTERESTED_NEXT_STEP"

    # 3. Filter by status: POSTPONED
    postponed_resp = await client.get("/api/v1/demos?status=POSTPONED", headers=headers)
    assert postponed_resp.status_code == 200
    p_items = postponed_resp.json()["data"]
    for item in p_items:
        assert item["status"] == "POSTPONED"


# ─────────────────────────────────────────────────────────────────────────────
# 5. HISTORICAL DEMOS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_historical_demo_creation_and_import(
    client: AsyncClient, db_session: AsyncSession
):
    """Test entering a historical demo and dry-run import preview."""
    user, token = await _create_test_user(db_session, role=UserRole.ADMIN, email_prefix="histadmin")
    company, contact = await _create_company_and_contact(db_session, owner_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    historical_dt = "2024-11-12T14:30:00Z"

    # 1. Create historical demo
    hist_resp = await client.post(
        "/api/v1/demos/historical",
        headers=headers,
        json={
            "contact_id": str(contact.id),
            "company_id": str(company.id),
            "historical_date": historical_dt,
            "status": "INTERESTED",
            "summary": "Historical demo conducted prior to CRM rollout.",
            "topics_covered": "Enterprise portal and custom integrations",
            "presenter": "Qusai",
            "attendees": "Board of Directors",
            "historical_source": "Sales Excel Archive 2024",
            "next_step": "Sign annual subscription",
        },
    )
    assert hist_resp.status_code == 201
    hist_data = hist_resp.json()["data"]
    assert hist_data["is_historical"] is True
    assert hist_data["historical_source"] == "Sales Excel Archive 2024"
    assert hist_data["presenter"] == "Qusai"

    # 2. Filter historical demos
    hist_list_resp = await client.get("/api/v1/demos?is_historical=true", headers=headers)
    assert hist_list_resp.status_code == 200
    hist_list = hist_list_resp.json()["data"]
    assert any(d["id"] == hist_data["id"] for d in hist_list)

    # 3. Test Import dry-run preview via CSV
    csv_text = (
        f"contact_email,Summary,Status,Next Step,Presenter,Demo Date\n"
        f"{contact.email},Imported historical session,INTERESTED,Review MSA,Saleh,2024-10-15\n"
        f"nonexistent@test.com,,PENDING,,,2024-10-15\n"
    )
    dry_run_resp = await client.post(
        "/api/v1/demos/import",
        headers=headers,
        files={"file": ("historical_import.csv", csv_text.encode("utf-8"), "text/csv")},
        data={"preview": "true"},
    )
    assert dry_run_resp.status_code == 200
    preview = dry_run_resp.json()
    assert preview["valid_count"] >= 1
    assert preview["error_count"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# 6. DASHBOARD METRICS & PERSONALIZED SCOPING
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connected_dashboard_kpis(client: AsyncClient, db_session: AsyncSession):
    """Test that /reports/dashboard delivers real demo status KPIs and my_metrics."""
    admin_user, admin_token = await _create_test_user(
        db_session, role=UserRole.ADMIN, email_prefix="dashadmin"
    )
    sales_user, sales_token = await _create_test_user(
        db_session, role=UserRole.SALES_USER, email_prefix="dashsales"
    )
    company, contact = await _create_company_and_contact(db_session, owner_id=sales_user.id)

    # Seed a demo assigned to sales_user
    demo_sales = Demo(
        company_id=company.id,
        contact_id=contact.id,
        owner_id=sales_user.id,
        scheduled_at=datetime.now(timezone.utc),
        status=DemoStatus.INTERESTED_NEXT_STEP,
        summary="Sales user closed demo",
        next_step="Send onboarding link",
        report_status=DemoReportStatus.REPORT_COMPLETE,
    )
    db_session.add(demo_sales)
    await db_session.flush()

    # 1. Sales user accesses dashboard -> sees personalized my_metrics
    sales_dash_resp = await client.get(
        "/api/v1/reports/dashboard",
        headers={"Authorization": f"Bearer {sales_token}"},
    )
    assert sales_dash_resp.status_code == 200
    sales_data = sales_dash_resp.json()["data"]
    assert "my_metrics" in sales_data
    my_m = sales_data["my_metrics"]
    assert my_m["my_total_demos"] >= 1
    assert my_m["my_interested"] >= 1

    # 2. Admin accesses dashboard -> sees full team demo breakdown
    admin_dash_resp = await client.get(
        "/api/v1/reports/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_dash_resp.status_code == 200
    admin_data = admin_dash_resp.json()["data"]
    assert "demos_total" in admin_data
    assert "demos_interested" in admin_data
    assert "demos_pending" in admin_data
    assert "demos_postponed" in admin_data
    assert "demos_needs_report" in admin_data
    assert "user_performance" in admin_data
