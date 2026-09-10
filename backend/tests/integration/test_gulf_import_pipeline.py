"""
tests/integration/test_gulf_import_pipeline.py

Integration tests for the Gulf Leads import pipeline.
Uses an in-memory SQLite database to verify:
- End-to-end import via run_import
- Idempotency (running twice produces 0 new inserts on the second run)
- Company reuse without duplicates
- Existing contact preservation (never overwrite existing notes/owner/calls)
- DNC contact preservation
- Sheet16 row 1 (Ayman Ali)
- SHAWARMER rows with empty salesperson -> UNASSIGNED status
- Row 67 invalid (empty col A) -> skipped and recorded in invalid_rows
- Legacy salesperson (Maria / Raneem) -> UNASSIGNED + awaiting_review
- Shared phone detection (different names -> conflict, not auto-merged)
- Excel import API endpoint (POST /api/v1/integrations/excel-import)
"""
import io
import pytest
import pytest_asyncio
import openpyxl
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact, ContactStatus
from app.models.company import Company
from app.models.call import Call
from app.models.user import User, UserRole
from app.core.security import hash_password, normalize_email, create_access_token
from app.imports.workbook_reader import LeadRow
from app.imports.normalizers import make_import_key
from app.imports.db_writer import run_import, load_db_snapshot, resolve_salesperson_map


@pytest_asyncio.fixture
async def setup_sales_team(db_session: AsyncSession):
    """Create real CRM users matching the salesperson map."""
    users = [
        User(
            email="saleh@alphapromena.com",
            normalized_email=normalize_email("saleh@alphapromena.com"),
            first_name="Saleh",
            last_name="Al-Ghamdi",
            password_hash=hash_password("Saleh123!"),
            role=UserRole.SALES_USER,
        ),
        User(
            email="hassan@alphapromena.com",
            normalized_email=normalize_email("hassan@alphapromena.com"),
            first_name="Hassan",
            last_name="Ali",
            password_hash=hash_password("Hassan123!"),
            role=UserRole.SALES_USER,
        ),
        User(
            email="aseel@alphapromena.com",
            normalized_email=normalize_email("aseel@alphapromena.com"),
            first_name="Aseel",
            last_name="Operations",
            password_hash=hash_password("Aseel123!"),
            role=UserRole.DATA_OPS,
        ),
    ]
    db_session.add_all(users)
    await db_session.flush()
    return {u.first_name.lower(): u for u in users}


@pytest.mark.asyncio
async def test_import_and_idempotency(db_session: AsyncSession, setup_sales_team):
    """Test importing contacts and verify idempotency on a second run."""
    team = setup_sales_team

    row1 = LeadRow(
        source_sheet="Leads",
        source_row=2,
        first_name="Tariq",
        last_name="Mansour",
        company="Apex Gulf",
        position="CTO",
        phone="+966551112233",
        normalized_phone="+966551112233",
        email="tariq@apexgulf.com",
        normalized_email="tariq@apexgulf.com",
        salesperson="Saleh",
        import_key=make_import_key(
            email="tariq@apexgulf.com",
            phone="+966551112233",
            first_name="Tariq",
            last_name="Mansour",
            company="Apex Gulf",
        ),
    )

    row2 = LeadRow(
        source_sheet="Leads",
        source_row=3,
        first_name="Mona",
        last_name="Zahrani",
        company="Apex Gulf",  # Same company -> should reuse
        position="COO",
        phone="+966554445566",
        normalized_phone="+966554445566",
        email="mona@apexgulf.com",
        normalized_email="mona@apexgulf.com",
        salesperson="Hassan",
        import_key=make_import_key(
            email="mona@apexgulf.com",
            phone="+966554445566",
            first_name="Mona",
            last_name="Zahrani",
            company="Apex Gulf",
        ),
    )

    # First run
    report1 = await run_import(db_session, [row1, row2], dry_run=False)
    assert report1.total_inserted == 2
    assert report1.total_updated == 0

    # Verify DB state
    contacts = (await db_session.execute(select(Contact))).scalars().all()
    assert len(contacts) == 2

    # Verify company reuse (only 1 company created for both contacts)
    companies = (await db_session.execute(select(Company))).scalars().all()
    assert len(companies) == 1
    assert companies[0].name.lower() == "apex gulf"

    # Verify ownership assignment
    tariq = next(c for c in contacts if c.first_name == "Tariq")
    assert tariq.owner_id == team["saleh"].id
    assert tariq.company_id == companies[0].id

    # Second run (Idempotency verification)
    report2 = await run_import(db_session, [row1, row2], dry_run=False)
    assert report2.total_inserted == 0
    assert report2.total_updated == 0
    assert report2.total_skipped == 2

    # Verify contact count remains unchanged
    contacts_after = (await db_session.execute(select(Contact))).scalars().all()
    assert len(contacts_after) == 2


@pytest.mark.asyncio
async def test_sheet16_row1_and_shawarmer_unassigned(db_session: AsyncSession, setup_sales_team):
    """Sheet16 row 1 (Ayman Ali) must be imported; SHAWARMER with empty salesperson -> UNASSIGNED."""
    row_ayman = LeadRow(
        source_sheet="Sheet16",
        source_row=1,
        first_name="Ayman",
        last_name="Ali",
        company="Future Tech",
        position="CEO",
        phone="+966509998877",
        normalized_phone="+966509998877",
        email="ayman@futuretech.sa",
        normalized_email="ayman@futuretech.sa",
        salesperson="Saleh",
        import_key=make_import_key(
            email="ayman@futuretech.sa",
            phone="+966509998877",
            first_name="Ayman",
            last_name="Ali",
            company="Future Tech",
        ),
    )

    row_shawarmer = LeadRow(
        source_sheet="Sheet16",
        source_row=693,
        first_name="Khaled",
        last_name="Shawarmer",
        company="SHAWARMER",
        position="Area Manager",
        phone="+966551239999",
        normalized_phone="+966551239999",
        email="",
        normalized_email="",
        salesperson="",  # Col F is empty
        status_hint="UNASSIGNED",
        import_key=make_import_key(
            email="",
            phone="+966551239999",
            first_name="Khaled",
            last_name="Shawarmer",
            company="SHAWARMER",
        ),
    )

    report = await run_import(db_session, [row_ayman, row_shawarmer], dry_run=False)
    assert report.total_inserted == 2

    # Check Ayman
    ayman_contact = (await db_session.execute(
        select(Contact).where(Contact.first_name == "Ayman")
    )).scalar_one()
    assert ayman_contact.owner_id is not None

    # Check Shawarmer contact is UNASSIGNED
    shawarmer_contact = (await db_session.execute(
        select(Contact).where(Contact.first_name == "Khaled")
    )).scalar_one()
    assert shawarmer_contact.owner_id is None
    assert shawarmer_contact.status == ContactStatus.UNASSIGNED


@pytest.mark.asyncio
async def test_invalid_row67_skipped(db_session: AsyncSession):
    """Row 67 in Sheet16 (no name, only activity text) must be skipped and logged."""
    row_67 = LeadRow(
        source_sheet="Sheet16",
        source_row=67,
        first_name="",
        last_name="",
        phone="",
        email="",
        is_invalid=True,
        invalid_reason="Column A is empty (no contact name)",
    )

    report = await run_import(db_session, [row_67], dry_run=False)
    assert report.total_invalid == 1
    assert report.total_inserted == 0
    assert len(report.invalid_rows) == 1
    assert report.invalid_rows[0]["sheet"] == "Sheet16"
    assert report.invalid_rows[0]["row"] == 67


@pytest.mark.asyncio
async def test_legacy_salesperson_maria(db_session: AsyncSession):
    """Maria/Raneem have no active CRM user -> UNASSIGNED status, reported in awaiting_review."""
    row_maria = LeadRow(
        source_sheet="Leads",
        source_row=12,
        first_name="Nasser",
        last_name="Al-Otaibi",
        company="Saudi Logistics",
        position="GM",
        phone="+966507778899",
        normalized_phone="+966507778899",
        email="nasser@logistics.sa",
        normalized_email="nasser@logistics.sa",
        salesperson="Maria",
        import_key=make_import_key(
            email="nasser@logistics.sa",
            phone="+966507778899",
            first_name="Nasser",
            last_name="Al-Otaibi",
            company="Saudi Logistics",
        ),
    )

    report = await run_import(db_session, [row_maria], dry_run=False)
    assert report.total_inserted == 1
    assert report.total_awaiting_review == 1
    assert len(report.awaiting_review_rows) == 1

    contact = (await db_session.execute(
        select(Contact).where(Contact.first_name == "Nasser")
    )).scalar_one()
    assert contact.owner_id is None
    assert contact.status == ContactStatus.UNASSIGNED


@pytest.mark.asyncio
async def test_dnc_contact_never_overwritten(db_session: AsyncSession, setup_sales_team):
    """A contact marked DNC must never be modified by import updates."""
    # Create existing DNC contact
    dnc_contact = Contact(
        first_name="DoNot",
        last_name="CallMe",
        phone="+966500000000",
        normalized_phone="+966500000000",
        email="dnc@test.com",
        normalized_email="dnc@test.com",
        is_dnc=True,
        notes="Customer requested DNC permanently",
        import_key="dnc_test_key",
    )
    db_session.add(dnc_contact)
    await db_session.flush()

    # Incoming row for same person with new details
    incoming = LeadRow(
        source_sheet="Leads",
        source_row=50,
        first_name="DoNot",
        last_name="CallMe",
        company="New Company",
        position="VP",
        phone="+966500000000",
        normalized_phone="+966500000000",
        email="dnc@test.com",
        normalized_email="dnc@test.com",
        salesperson="Saleh",
        notes="Overwrite attempt",
        import_key="dnc_test_key",
    )

    report = await run_import(db_session, [incoming], dry_run=False)
    assert report.total_inserted == 0
    assert report.total_updated == 0
    assert report.total_skipped == 1

    # Reload from DB
    await db_session.refresh(dnc_contact)
    assert dnc_contact.notes == "Customer requested DNC permanently"
    assert dnc_contact.position is None


@pytest.mark.asyncio
async def test_shared_phone_conflict_detection(db_session: AsyncSession):
    """Same phone with different names must be flagged as conflict, not merged."""
    # Contact 1 in DB
    c1 = Contact(
        first_name="Ahmed",
        last_name="K",
        phone="+966512345678",
        normalized_phone="+966512345678",
        import_key="key_ahmed",
    )
    db_session.add(c1)
    await db_session.flush()

    # Incoming row with same phone but different person (Salem)
    incoming = LeadRow(
        source_sheet="Leads",
        source_row=88,
        first_name="Salem",
        last_name="M",
        phone="+966512345678",
        normalized_phone="+966512345678",
        salesperson="",
        import_key="key_salem",
    )

    report = await run_import(db_session, [incoming], dry_run=False)
    assert report.total_conflicts == 1
    assert len(report.conflict_rows) == 1
    assert "Salem" in report.conflict_rows[0]["name"]


@pytest.mark.asyncio
async def test_excel_import_endpoint(client, db_session: AsyncSession, setup_sales_team):
    """Test POST /api/v1/integrations/excel-import with a generated .xlsx file."""
    team = setup_sales_team
    aseel_user = team["aseel"]
    token = create_access_token(aseel_user.id, aseel_user.role.value)

    # Build an in-memory workbook with Leads sheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    # Header
    ws.append(["Name", "Company", "Position", "Phone", "Email", "Salesperson", "Attempt 1", "Attempt 2", "Attempt 3"])
    # Row 1
    ws.append(["Sultan Al-Obeid", "Gulf Horizons", "Director", "+966541112222", "sultan@gulfhorizons.com", "Saleh", "Called interested", None, None])

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    # 1. Dry run
    res_dry = await client.post(
        "/api/v1/integrations/excel-import",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test_gulf.xlsx", bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"dry_run": "true"},
    )
    assert res_dry.status_code == 200
    data_dry = res_dry.json()
    assert data_dry["dry_run"] is True
    assert data_dry["report"]["summary"]["total_inserted"] == 0

    # 2. Actual import
    res_actual = await client.post(
        "/api/v1/integrations/excel-import",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test_gulf.xlsx", bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"dry_run": "false"},
    )
    assert res_actual.status_code == 200
    data_actual = res_actual.json()
    assert data_actual["dry_run"] is False
    assert data_actual["report"]["summary"]["total_inserted"] == 1

    # Verify contact owner is Saleh, NOT Aseel (who uploaded the file)
    contact = (await db_session.execute(
        select(Contact).where(Contact.first_name == "Sultan")
    )).scalar_one()
    assert contact.owner_id == team["saleh"].id
    assert contact.owner_id != aseel_user.id
