"""
Demos router — stage & status tracking, mandatory reporting, conditional outcome validation,
status counts, historical demo entry & import, and role-scoped filtering.
"""
import io
import csv
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Request
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.demo import Demo, DemoStage, DemoStatus, DemoReportStatus
from app.models.contact import Contact
from app.models.company import Company
from app.models.user import User
from app.models.audit import AuditLog
from app.audit.service import AuditService
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from app.core.security import normalize_email

router = APIRouter(prefix="/demos", tags=["Demos"])


class DemoCreateBody(BaseModel):
    contact_id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    owner_id: Optional[str] = None
    status: str = DemoStatus.PENDING
    stage: Optional[str] = None
    scheduled_at: Optional[str] = None
    presenter: Optional[str] = None
    attendees: Optional[str] = None
    topics_covered: Optional[str] = None
    summary: Optional[str] = None
    result: Optional[str] = None
    reason: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_date: Optional[str] = None
    notes: Optional[str] = None
    is_historical: bool = False
    historical_date: Optional[str] = None
    historical_source: Optional[str] = None


class DemoUpdateBody(BaseModel):
    owner_id: Optional[str] = None
    status: Optional[str] = None
    stage: Optional[str] = None
    scheduled_at: Optional[str] = None
    completed_at: Optional[str] = None
    presenter: Optional[str] = None
    attendees: Optional[str] = None
    topics_covered: Optional[str] = None
    summary: Optional[str] = None
    result: Optional[str] = None
    reason: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_date: Optional[str] = None
    notes: Optional[str] = None
    report_status: Optional[str] = None


class DemoReportSubmitBody(BaseModel):
    summary: str
    status: str
    presenter: Optional[str] = None
    attendees: Optional[str] = None
    topics_covered: Optional[str] = None
    result: Optional[str] = None
    reason: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_date: Optional[str] = None
    notes: Optional[str] = None


def _validate_demo_report_rules(status: str, summary: Optional[str], reason: Optional[str], next_step: Optional[str]) -> tuple[bool, str]:
    """
    Validates mandatory business report rules:
    - Interested/Next Step requires a next step.
    - Postponed requires a reason.
    - Not Interested requires a reason.
    - Cancelled requires a cancellation reason.
    - Pending requires explanation or follow-up note.
    """
    s = (summary or "").strip()
    st = status.upper()

    if st in ("INTERESTED_NEXT_STEP", "INTERESTED"):
        if not next_step or not next_step.strip():
            return False, "Interested / Next Step demos require an explicit next step."

    elif st in ("POSTPONED", "RESCHEDULED"):
        if not reason or not reason.strip():
            return False, "Postponed demos require a reason explaining the postponement."

    elif st in ("NOT_INTERESTED", "LOST"):
        if not reason or not reason.strip():
            return False, "Not Interested demos require a reason explaining why the prospect declined."

    elif st in ("CANCELLED", "NO_SHOW"):
        if not reason or not reason.strip():
            return False, "Cancelled demos require a cancellation reason."

    elif st == "PENDING":
        if not next_step or not next_step.strip():
            return False, "Pending demos require a clear follow-up action or next step."

    return True, ""


def _demo_dict(d: Demo) -> dict:
    c_name = d.contact.full_name if d.contact else None
    comp_name = (
        d.company.name
        if d.company
        else (d.contact.company.name if (d.contact and d.contact.company) else None)
    )
    return {
        "id": str(d.id),
        "contact_id": str(d.contact_id),
        "contact_name": c_name,
        "contact_phone": d.contact.phone if d.contact else None,
        "contact_email": d.contact.email if d.contact else None,
        "company_id": str(d.company_id) if d.company_id else None,
        "company_name": comp_name,
        "owner_id": str(d.owner_id) if d.owner_id else None,
        "owner_name": d.owner.full_name if d.owner else "Unassigned",
        "stage": d.stage,
        "status": d.status,
        "scheduled_at": d.scheduled_at.isoformat() if d.scheduled_at else None,
        "completed_at": d.completed_at.isoformat() if d.completed_at else None,
        "cancelled_at": d.cancelled_at.isoformat() if d.cancelled_at else None,
        "presenter": d.presenter,
        "attendees": d.attendees,
        "topics_covered": d.topics_covered,
        "summary": d.summary,
        "result": d.result,
        "reason": d.reason,
        "next_step": d.next_step,
        "next_step_due_date": d.next_step_due_date.isoformat() if d.next_step_due_date else None,
        "notes": d.notes,
        "report_status": d.report_status,
        "is_historical": d.is_historical,
        "historical_source": d.historical_source,
        "historical_date": d.historical_date.isoformat() if d.historical_date else None,
        "created_by_id": str(d.created_by_id) if d.created_by_id else None,
        "updated_by_id": str(d.updated_by_id) if d.updated_by_id else None,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


def _build_demo_query(
    current_user: User,
    status: Optional[str] = None,
    report_status: Optional[str] = None,
    is_historical: Optional[bool] = None,
    owner_id: Optional[str] = None,
    user_id: Optional[str] = None,
    company_id: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    stmt = (
        select(Demo)
        .options(
            selectinload(Demo.contact).selectinload(Contact.company),
            selectinload(Demo.company),
            selectinload(Demo.owner),
        )
    )

    # Permission scoping: Regular user sees own assigned demos; managers/admins see team
    target_user = owner_id or user_id
    if not current_user.is_manager_or_above:
        stmt = stmt.where(Demo.owner_id == current_user.id)
    elif target_user:
        stmt = stmt.where(Demo.owner_id == uuid.UUID(target_user))

    # Status filter
    if status and status.upper() != "ALL":
        st = status.upper()
        if st in ("INTERESTED", "NEXT_STEP", "INTERESTED_NEXT_STEP"):
            stmt = stmt.where(Demo.status.in_(["INTERESTED_NEXT_STEP", "INTERESTED"]))
        elif st in ("NOT_INTERESTED", "LOST"):
            stmt = stmt.where(Demo.status.in_(["NOT_INTERESTED", "LOST"]))
        elif st in ("CANCELLED", "NO_SHOW"):
            stmt = stmt.where(Demo.status.in_(["CANCELLED", "NO_SHOW"]))
        elif st in ("POSTPONED", "RESCHEDULED"):
            stmt = stmt.where(Demo.status.in_(["POSTPONED", "RESCHEDULED"]))
        elif st == "PENDING":
            stmt = stmt.where(Demo.status.in_(["PENDING", "REQUESTED", "SCHEDULED"]))
        else:
            stmt = stmt.where(Demo.status == st)

    # Report Status filter
    if report_status:
        stmt = stmt.where(Demo.report_status == report_status.upper())

    # Historical filter
    if is_historical is not None:
        stmt = stmt.where(Demo.is_historical.is_(is_historical))

    # Company filter
    if company_id:
        stmt = stmt.where(Demo.company_id == uuid.UUID(company_id))

    # Search filter across contact name, company name, owner name
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.join(Contact, Demo.contact_id == Contact.id).outerjoin(Company, Demo.company_id == Company.id).outerjoin(User, Demo.owner_id == User.id)
        stmt = stmt.where(
            or_(
                Contact.first_name.ilike(term),
                Contact.last_name.ilike(term),
                Company.name.ilike(term),
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                Demo.summary.ilike(term),
                Demo.notes.ilike(term),
            )
        )

    # Date range filter (on scheduled_at or historical_date)
    if date_from:
        try:
            df = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            stmt = stmt.where(or_(Demo.scheduled_at >= df, Demo.historical_date >= df))
        except Exception:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
            stmt = stmt.where(or_(Demo.scheduled_at <= dt, Demo.historical_date <= dt))
        except Exception:
            pass

    return stmt


@router.get("")
async def list_demos(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    report_status: Optional[str] = Query(None),
    is_historical: Optional[bool] = Query(None),
    user_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List demos with pagination, search, status, and historical filtering."""
    stmt = _build_demo_query(
        current_user=current_user,
        status=status,
        report_status=report_status,
        is_historical=is_historical,
        owner_id=owner_id,
        user_id=user_id,
        company_id=company_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    # Order by scheduled/historical date descending
    stmt = (
        stmt.order_by(
            func.coalesce(Demo.scheduled_at, Demo.historical_date, Demo.created_at).desc()
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    demos = (await db.execute(stmt)).scalars().all()
    return {
        "data": [_demo_dict(d) for d in demos],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": -(-total // per_page) if per_page else 1,
        },
    }


@router.get("/counts")
async def get_demo_counts(
    owner_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated counts for all demo tabs matching the exact query logic:
    All, Interested / Next Step, Not Interested, Cancelled, Postponed, Pending, Needs Report, Historical.
    """
    target_user = owner_id or user_id
    base_where = []
    if not current_user.is_manager_or_above:
        base_where.append(Demo.owner_id == current_user.id)
    elif target_user:
        base_where.append(Demo.owner_id == uuid.UUID(target_user))

    # Base query
    base_stmt = select(Demo)
    if base_where:
        base_stmt = base_stmt.where(*base_where)

    rows = (await db.execute(base_stmt)).scalars().all()

    counts = {
        "ALL": len(rows),
        "all": len(rows),
        "INTERESTED_NEXT_STEP": len([r for r in rows if r.status in ("INTERESTED_NEXT_STEP", "INTERESTED")]),
        "interested": len([r for r in rows if r.status in ("INTERESTED_NEXT_STEP", "INTERESTED")]),
        "NOT_INTERESTED": len([r for r in rows if r.status in ("NOT_INTERESTED", "LOST")]),
        "not_interested": len([r for r in rows if r.status in ("NOT_INTERESTED", "LOST")]),
        "CANCELLED": len([r for r in rows if r.status in ("CANCELLED", "NO_SHOW")]),
        "cancelled": len([r for r in rows if r.status in ("CANCELLED", "NO_SHOW")]),
        "POSTPONED": len([r for r in rows if r.status in ("POSTPONED", "RESCHEDULED")]),
        "postponed": len([r for r in rows if r.status in ("POSTPONED", "RESCHEDULED")]),
        "PENDING": len([r for r in rows if r.status in ("PENDING", "REQUESTED", "SCHEDULED")]),
        "pending": len([r for r in rows if r.status in ("PENDING", "REQUESTED", "SCHEDULED")]),
        "NEEDS_REPORT": len([r for r in rows if r.report_status == "NEEDS_REPORT"]),
        "needs_report": len([r for r in rows if r.report_status == "NEEDS_REPORT"]),
        "REPORT_COMPLETE": len([r for r in rows if r.report_status == "REPORT_COMPLETE"]),
        "report_complete": len([r for r in rows if r.report_status == "REPORT_COMPLETE"]),
        "HISTORICAL": len([r for r in rows if r.is_historical]),
        "historical": len([r for r in rows if r.is_historical]),
    }
    return {"data": counts}


@router.post("", status_code=201)
async def create_demo(
    body: DemoCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new demo.
    Enforces mandatory summary if marking as complete.
    Enforces required owner and scheduled date.
    """
    target_owner = uuid.UUID(body.owner_id) if body.owner_id else current_user.id
    contact_uuid = uuid.UUID(body.contact_id)

    # Check contact exists
    contact = (await db.execute(select(Contact).where(Contact.id == contact_uuid))).scalar_one_or_none()
    if not contact:
        raise NotFoundError("Contact not found.")

    comp_id = uuid.UUID(body.company_id) if body.company_id else contact.company_id

    # Parse dates
    sched_dt = None
    if body.scheduled_at:
        sched_dt = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
    elif body.historical_date:
        sched_dt = datetime.fromisoformat(body.historical_date.replace("Z", "+00:00"))
    else:
        sched_dt = datetime.now(timezone.utc)

    hist_dt = datetime.fromisoformat(body.historical_date.replace("Z", "+00:00")) if body.historical_date else None
    next_due = datetime.fromisoformat(body.next_step_due_date.replace("Z", "+00:00")) if body.next_step_due_date else None

    # Status normalization
    norm_status = body.status.upper() if body.status else DemoStatus.PENDING
    if norm_status in ("INTERESTED", "NEXT_STEP"):
        norm_status = DemoStatus.INTERESTED_NEXT_STEP

    # Determine report status: every new demo requires a non-empty summary report
    has_summary = bool(body.summary and body.summary.strip())
    if not has_summary:
        raise ValidationError("Every new demo requires a non-empty summary report.")
    report_status = DemoReportStatus.REPORT_COMPLETE

    # Validate business rules
    valid_rules, err_rule = _validate_demo_report_rules(
        norm_status, body.summary, body.reason, body.next_step
    )
    if not valid_rules:
        raise ValidationError(err_rule)

    demo = Demo(
        contact_id=contact_uuid,
        company_id=comp_id,
        owner_id=target_owner,
        stage=body.stage or (DemoStage.COMPLETED if norm_status in ("INTERESTED_NEXT_STEP", "NOT_INTERESTED") else DemoStage.SCHEDULED),
        status=norm_status,
        scheduled_at=sched_dt,
        presenter=body.presenter or current_user.full_name,
        attendees=body.attendees,
        topics_covered=body.topics_covered,
        summary=body.summary.strip() if body.summary else None,
        result=body.result,
        reason=body.reason,
        next_step=body.next_step,
        next_step_due_date=next_due,
        notes=body.notes,
        report_status=report_status,
        is_historical=body.is_historical,
        historical_source=body.historical_source,
        historical_date=hist_dt or (sched_dt if body.is_historical else None),
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    if norm_status in ("INTERESTED_NEXT_STEP", "NOT_INTERESTED", "COMPLETED") and not demo.completed_at:
        demo.completed_at = sched_dt or datetime.now(timezone.utc)
    elif norm_status == "CANCELLED" and not demo.cancelled_at:
        demo.cancelled_at = sched_dt or datetime.now(timezone.utc)

    db.add(demo)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="demo.created" if not body.is_historical else "demo.historical_created",
        entity_type="demo",
        actor_id=current_user.id,
        entity_id=demo.id,
        new_value={"status": demo.status, "summary": demo.summary, "is_historical": demo.is_historical},
        notes=f"Demo logged for contact {contact.full_name}",
    )

    # Re-fetch
    stmt = (
        select(Demo)
        .where(Demo.id == demo.id)
        .options(
            selectinload(Demo.contact).selectinload(Contact.company),
            selectinload(Demo.company),
            selectinload(Demo.owner),
        )
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _demo_dict(loaded)}


@router.post("/historical", status_code=201)
async def create_historical_demo(
    body: DemoCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Explicitly create a historical demo that took place before the CRM rollout.
    Preserves historical date separately from database created_at timestamp.
    """
    body.is_historical = True
    if not body.historical_date and body.scheduled_at:
        body.historical_date = body.scheduled_at
    elif not body.historical_date:
        raise ValidationError("Historical demo requires the actual date the demo took place.")

    return await create_demo(body, current_user, db)


@router.patch("/{demo_id}")
async def update_demo(
    demo_id: uuid.UUID,
    body: DemoUpdateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update demo details, status, or assignee with permission checks."""
    stmt = (
        select(Demo)
        .where(Demo.id == demo_id)
        .options(
            selectinload(Demo.contact).selectinload(Contact.company),
            selectinload(Demo.company),
            selectinload(Demo.owner),
        )
    )
    demo = (await db.execute(stmt)).scalar_one_or_none()
    if not demo:
        raise NotFoundError("Demo not found.")

    if not current_user.is_manager_or_above and demo.owner_id != current_user.id:
        raise ForbiddenError("You do not have permission to edit this demo.")

    old_status = demo.status
    old_summary = demo.summary

    if body.status:
        demo.status = body.status.upper()
    if body.stage:
        demo.stage = body.stage
    if body.presenter is not None:
        demo.presenter = body.presenter
    if body.attendees is not None:
        demo.attendees = body.attendees
    if body.topics_covered is not None:
        demo.topics_covered = body.topics_covered
    if body.summary is not None:
        demo.summary = body.summary.strip() if body.summary else None
    if body.result is not None:
        demo.result = body.result
    if body.reason is not None:
        demo.reason = body.reason
    if body.next_step is not None:
        demo.next_step = body.next_step
    if body.notes is not None:
        demo.notes = body.notes
    if body.scheduled_at:
        demo.scheduled_at = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
    if body.completed_at:
        demo.completed_at = datetime.fromisoformat(body.completed_at.replace("Z", "+00:00"))
    if body.next_step_due_date:
        demo.next_step_due_date = datetime.fromisoformat(body.next_step_due_date.replace("Z", "+00:00"))
    if body.owner_id:
        demo.owner_id = uuid.UUID(body.owner_id)

    # Validate report rules if status changed or report completed
    if demo.summary and demo.summary.strip():
        valid_rules, err_rule = _validate_demo_report_rules(
            demo.status, demo.summary, demo.reason, demo.next_step
        )
        if not valid_rules:
            raise ValidationError(err_rule)
        demo.report_status = DemoReportStatus.REPORT_COMPLETE
    else:
        demo.report_status = DemoReportStatus.NEEDS_REPORT

    demo.updated_by_id = current_user.id
    db.add(demo)
    await db.flush()

    audit = AuditService(db)
    if body.status and body.status != old_status:
        await audit.log(
            action="demo.status_changed",
            entity_type="demo",
            actor_id=current_user.id,
            entity_id=demo.id,
            old_value={"status": old_status},
            new_value={"status": demo.status, "reason": demo.reason},
        )
    elif not old_summary and demo.summary:
        await audit.log(
            action="demo.report_completed",
            entity_type="demo",
            actor_id=current_user.id,
            entity_id=demo.id,
            new_value={"report_status": demo.report_status, "summary": demo.summary},
        )

    reloaded = (await db.execute(stmt)).scalar_one()
    return {"data": _demo_dict(reloaded)}


@router.patch("/{demo_id}/report")
async def submit_demo_report(
    demo_id: uuid.UUID,
    body: DemoReportSubmitBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete a demo report with mandatory summary and outcome validation."""
    if not body.summary or not body.summary.strip():
        raise ValidationError("Demo summary is required to complete a demo report.")

    valid_rules, err_rule = _validate_demo_report_rules(
        body.status, body.summary, body.reason, body.next_step
    )
    if not valid_rules:
        raise ValidationError(err_rule)

    update_payload = DemoUpdateBody(
        summary=body.summary,
        status=body.status,
        presenter=body.presenter,
        attendees=body.attendees,
        topics_covered=body.topics_covered,
        result=body.result,
        reason=body.reason,
        next_step=body.next_step,
        next_step_due_date=body.next_step_due_date,
        notes=body.notes,
        report_status=DemoReportStatus.REPORT_COMPLETE,
    )
    return await update_demo(demo_id, update_payload, current_user, db)


@router.post("/import")
async def import_historical_demos(
    file: UploadFile = File(...),
    preview: bool = Form(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Import historical demo records from CSV/XLSX.
    When preview=True, validates rows and checks for duplicates without committing.
    When preview=False, executes transaction and commits valid records.
    """
    content = await file.read()
    filename = file.filename or "import.csv"

    rows_data: List[Dict[str, str]] = []
    if filename.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            rows_data.append({k.strip(): (v or "").strip() for k, v in r.items() if k})
    else:
        # Excel format
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
        headers = [str(cell.value or "").strip() for cell in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            r_dict = {}
            for h, val in zip(headers, row):
                if h:
                    r_dict[h] = str(val or "").strip()
            if any(r_dict.values()):
                rows_data.append(r_dict)

    if not rows_data:
        raise ValidationError("No data rows found in uploaded file.")

    validated_records = []
    errors = []

    for idx, row in enumerate(rows_data, start=2):
        row_errs = []
        # Find contact by email, phone, or name
        c_email = row.get("Email") or row.get("contact_email") or row.get("email")
        c_name = row.get("Contact Name") or row.get("contact_name") or row.get("name")
        c_phone = row.get("Phone") or row.get("phone")
        comp_name = row.get("Company") or row.get("company_name") or row.get("company")
        demo_date_str = row.get("Demo Date") or row.get("demo_date") or row.get("date")
        summary = row.get("Summary") or row.get("summary")
        status = (row.get("Status") or row.get("status") or "INTERESTED_NEXT_STEP").upper()
        presenter = row.get("Presenter") or row.get("presenter") or current_user.full_name
        attendees = row.get("Attendees") or row.get("attendees")
        next_step = row.get("Next Step") or row.get("next_step")
        reason = row.get("Reason") or row.get("reason")

        contact = None
        if c_email:
            norm_c = normalize_email(c_email)
            contact = (await db.execute(select(Contact).where(or_(Contact.normalized_email == norm_c, func.lower(Contact.email) == norm_c)))).scalar_one_or_none()
        if not contact and c_name:
            contact = (await db.execute(select(Contact).where(func.lower(Contact.first_name + " " + func.coalesce(Contact.last_name, "")) == c_name.lower()))).scalar_one_or_none()

        if not contact:
            row_errs.append(f"Row {idx}: Contact '{c_email or c_name or 'unspecified'}' could not be matched to an existing CRM contact.")

        demo_dt = None
        if demo_date_str:
            try:
                demo_dt = datetime.fromisoformat(demo_date_str.replace("Z", "+00:00"))
            except Exception:
                try:
                    demo_dt = datetime.strptime(demo_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except Exception:
                    row_errs.append(f"Row {idx}: Invalid date format '{demo_date_str}'. Expected YYYY-MM-DD.")
        else:
            row_errs.append(f"Row {idx}: Demo Date is required.")

        if not summary or not summary.strip():
            row_errs.append(f"Row {idx}: Mandatory summary is missing.")

        val_rule, err_r = _validate_demo_report_rules(status, summary, reason, next_step)
        if not val_rule:
            row_errs.append(f"Row {idx}: {err_r}")

        if row_errs:
            errors.extend(row_errs)
        else:
            validated_records.append({
                "contact_id": contact.id,
                "contact_name": contact.full_name,
                "company_id": contact.company_id,
                "company_name": comp_name or (contact.company.name if contact.company else None),
                "scheduled_at": demo_dt,
                "historical_date": demo_dt,
                "presenter": presenter,
                "attendees": attendees,
                "summary": summary,
                "status": status,
                "reason": reason,
                "next_step": next_step,
                "is_historical": True,
                "historical_source": filename,
            })

    if preview:
        return {
            "preview": True,
            "total_rows": len(rows_data),
            "valid_count": len(validated_records),
            "error_count": len(errors),
            "errors": errors[:50],  # cap to top 50
            "sample_valid": validated_records[:5],
        }

    if errors:
        raise ValidationError(f"Import failed with {len(errors)} validation errors. Please resolve errors before importing.")

    # Commit records
    inserted_count = 0
    for item in validated_records:
        new_d = Demo(
            contact_id=item["contact_id"],
            company_id=item["company_id"],
            owner_id=current_user.id,
            stage=DemoStage.COMPLETED,
            status=item["status"],
            scheduled_at=item["scheduled_at"],
            historical_date=item["historical_date"],
            completed_at=item["scheduled_at"],
            presenter=item["presenter"],
            attendees=item["attendees"],
            summary=item["summary"],
            reason=item["reason"],
            next_step=item["next_step"],
            report_status=DemoReportStatus.REPORT_COMPLETE,
            is_historical=True,
            historical_source=item["historical_source"],
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
        )
        db.add(new_d)
        inserted_count += 1

    await db.flush()
    return {
        "preview": False,
        "imported_count": inserted_count,
        "message": f"Successfully imported {inserted_count} historical demos.",
    }
