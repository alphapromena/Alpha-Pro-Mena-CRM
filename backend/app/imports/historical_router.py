"""
Drag-and-drop import of historical demos and follow-ups.

Two endpoints, deliberately separate:

  POST /api/v1/imports/historical/preview   parses and reports, writes nothing
  POST /api/v1/imports/historical/commit    writes, in one transaction

Nothing is ever written by the preview, so the user sees exactly what would
happen before deciding. The commit requires the checksum the preview returned,
so it cannot silently act on a different file than the one that was reviewed.

Re-uploading the same workbook inserts nothing, enforced by a unique index on
import_key rather than by a check here.
"""
from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import openpyxl
import structlog
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import ValidationError
from app.database import get_db
from app.imports.historical_activity import (
    ACTIVITY_DEMO,
    ACTIVITY_FOLLOWUP,
    DEMO_SHEET,
    FOLLOWUP_SHEETS,
    ActivityRow,
    dedupe_key,
    parse_workbook,
)
from app.imports.identity import ContactIndex, Identity, norm_company
from app.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/imports/historical", tags=["Historical Import"])

MAX_BYTES = 50 * 1024 * 1024
CANONICAL_OWNERS = {
    "saleh": "saleh@alphapromena.com",
    "hassan": "hassan@alphapromena.com",
    "hasan": "hassan@alphapromena.com",
    "amin": "amin@alphapromena.com",
    "ghaida": "ghaida@alphapromena.com",
    "qusai": "qusai@alphapromena.com",
    "aseel": "aseel@alphapromena.com",
    "abdallah": "abdallah@alphapromena.com",
}


async def _read_upload(file: UploadFile, kind: Optional[str]) -> tuple[Any, str, str]:
    """
    Accept a workbook or a single CSV sheet.

    Returns (workbook_like, checksum, source_label). A CSV has no worksheets, so
    it cannot say whether it holds demos or follow-ups; the caller supplies that
    from the page the drop happened on.
    """
    name = (file.filename or "").lower()
    content = await file.read()
    if not content:
        raise ValidationError("The uploaded file is empty.")
    if len(content) > MAX_BYTES:
        raise ValidationError("File is larger than 50 MB.")
    checksum = hashlib.sha256(content).hexdigest()

    if name.endswith((".xlsx", ".xlsm")):
        try:
            return openpyxl.load_workbook(io.BytesIO(content), data_only=True), checksum, "workbook"
        except Exception as exc:
            raise ValidationError(f"Could not read the workbook: {exc}")

    if name.endswith(".csv"):
        if kind not in (ACTIVITY_DEMO, ACTIVITY_FOLLOWUP):
            raise ValidationError(
                "A CSV has no sheet names, so it cannot say whether it holds demos or "
                "follow-ups. Drop it on the Demos or Follow-ups page, or upload the "
                ".xlsx workbook instead."
            )
        return _csv_as_sheet(content, kind), checksum, "csv"

    if name.endswith(".xls"):
        raise ValidationError(
            "The old .xls format is not supported. Open it in Excel and use "
            "File > Save As > Excel Workbook (.xlsx), then try again."
        )

    raise ValidationError(
        "Unsupported file type. Upload an .xlsx workbook, or a .csv laid out like the "
        "activity sheets: name, company, position, phone, email, salesperson, then the "
        "outcome columns."
    )


class _CsvWorkbook:
    """
    Minimal stand-in so a CSV can go through the same parser as a worksheet.

    The parser only ever asks for sheetnames and iter_rows, so nothing more is
    needed and the CSV path cannot drift from the workbook path.
    """

    def __init__(self, sheet_name: str, rows: List[tuple]) -> None:
        self.sheetnames = [sheet_name]
        self._sheets = {sheet_name: _CsvSheet(rows)}

    def __getitem__(self, name: str):
        return self._sheets[name]


class _CsvSheet:
    def __init__(self, rows: List[tuple]) -> None:
        self._rows = rows

    def iter_rows(self, values_only: bool = True):
        return iter(self._rows)


def _csv_as_sheet(content: bytes, kind: str) -> _CsvWorkbook:
    import csv as _csv

    text = content.decode("utf-8-sig", errors="replace")
    rows = [tuple(r) for r in _csv.reader(io.StringIO(text))]
    if not rows:
        raise ValidationError("The CSV has no rows.")

    # A header row is optional. Drop it only when the first cell clearly labels a
    # column rather than naming a person, so a headerless export keeps every row.
    first = (rows[0][0] or "").strip().lower() if rows[0] else ""
    if first in {"name", "contact", "contact name", "full name"}:
        rows = rows[1:]

    sheet_name = DEMO_SHEET if kind == ACTIVITY_DEMO else FOLLOWUP_SHEETS[0]
    return _CsvWorkbook(sheet_name, rows)


async def _resolve(db: AsyncSession, rows: List[ActivityRow], checksum: str) -> Dict[str, Any]:
    """Match every parsed row to a contact, company and owner. Reads only."""
    from app.models.company import Company
    from app.models.contact import Contact

    owners = {
        r.email: r.id
        for r in (await db.execute(select(User.id, User.email).where(User.deleted_at.is_(None)))).all()
    }
    companies = {
        norm_company(r.name): r.id
        for r in (await db.execute(select(Company.id, Company.name).where(Company.deleted_at.is_(None)))).all()
        if r.name
    }

    # Historical activity is matched against every contact, including archived
    # ones. A demo that happened is still history even if the person was retired
    # from the active list by the Sheet16 reconciliation; refusing to link it
    # would throw that history away. Archived matches are flagged, not blocked.
    contacts = (await db.execute(select(Contact))).scalars().all()
    company_names = {
        r.id: norm_company(r.name)
        for r in (await db.execute(select(Company.id, Company.name))).all()
        if r.name
    }
    index = ContactIndex()
    handles: Dict[int, Any] = {}
    for c in contacts:
        marker = object()
        handles[id(marker)] = c
        index.add(
            Identity.build(
                email=c.email, phone=c.phone,
                name=f"{c.first_name or ''} {c.last_name or ''}",
                company=company_names.get(c.company_id, ""),
            ),
            marker,
        )

    existing_keys = {
        r[0]
        for r in (await db.execute(text(
            "select import_key from demos where import_key is not null "
            "union all select import_key from follow_ups where import_key is not null"
        ))).all()
    }

    resolved: List[Dict[str, Any]] = []
    for row in rows:
        key = dedupe_key(checksum, row)
        hit, rule = index.match(
            Identity.build(email=row.email, phone=row.phone, name=row.name, company=row.company)
        )
        contact = handles[id(hit)] if hit is not None else None
        owner_email = CANONICAL_OWNERS.get(row.owner_raw.lower())
        problems = list(row.problems)
        if contact is None:
            problems.append("no matching contact")
        elif contact.deleted_at is not None:
            problems.append("contact is archived")
        if row.company and norm_company(row.company) not in companies:
            problems.append("company not in master list")
        if owner_email and owner_email not in owners:
            problems.append("salesperson has no account")

        owner_conflict = bool(
            contact is not None
            and owner_email
            and contact.owner_id
            and owners.get(owner_email)
            and str(contact.owner_id) != str(owners[owner_email])
        )

        resolved.append({
            "import_key": key,
            "row": row,
            "contact_id": str(contact.id) if contact else None,
            "contact_name": f"{contact.first_name} {contact.last_name}".strip() if contact else None,
            "match_rule": rule,
            "company_id": str(companies[norm_company(row.company)]) if row.company and norm_company(row.company) in companies else None,
            "owner_id": str(owners[owner_email]) if owner_email and owner_email in owners else None,
            "owner_email": owner_email,
            "owner_conflict": owner_conflict,
            "already_imported": key in existing_keys,
            "problems": problems,
            "importable": contact is not None and row.is_importable and key not in existing_keys,
        })
    return {"resolved": resolved, "existing_keys": len(existing_keys)}


def _summarise(resolved: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total": len(resolved),
        "ready": sum(1 for r in resolved if r["importable"]),
        "already_imported": sum(1 for r in resolved if r["already_imported"]),
        "missing_contact": sum(1 for r in resolved if "no matching contact" in r["problems"]),
        "archived_contact": sum(1 for r in resolved if "contact is archived" in r["problems"]),
        "missing_company": sum(1 for r in resolved if "company not in master list" in r["problems"]),
        "missing_date": sum(1 for r in resolved if r["row"].missing_date),
        "owner_conflicts": sum(1 for r in resolved if r["owner_conflict"]),
        "invalid": sum(1 for r in resolved if not r["row"].is_importable),
        "demos": sum(1 for r in resolved if r["row"].activity_type == ACTIVITY_DEMO and r["importable"]),
        "follow_ups": sum(1 for r in resolved if r["row"].activity_type == ACTIVITY_FOLLOWUP and r["importable"]),
    }


def _as_json(entry: Dict[str, Any]) -> Dict[str, Any]:
    row: ActivityRow = entry["row"]
    return {
        "sheet": row.sheet,
        "source_row": row.source_row,
        "activity_type": row.activity_type,
        "name": row.name,
        "company": row.company,
        "email": row.email,
        "phone": row.phone,
        "salesperson": row.owner_raw,
        "activity_date": row.activity_date.isoformat() if row.activity_date else None,
        "outcome": row.outcome,
        "notes": row.notes,
        "next_step": row.next_step,
        "matched_contact": entry["contact_name"],
        "match_rule": entry["match_rule"],
        "owner_conflict": entry["owner_conflict"],
        "already_imported": entry["already_imported"],
        "problems": entry["problems"],
        "importable": entry["importable"],
    }


@router.post("/preview")
async def preview_historical_import(
    file: UploadFile = File(...),
    kind: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Parse the upload and report what would happen. Writes nothing."""
    wb, checksum, _ = await _read_upload(file, kind)
    parsed = parse_workbook(wb, checksum)
    if not parsed["rows"]:
        raise ValidationError(
            "No supported activity worksheets found. Expected Demo, Ghaida fu or Amin fu."
        )

    resolved = (await _resolve(db, parsed["rows"], checksum))["resolved"]
    logger.info(
        "historical_import.preview",
        user_id=str(current_user.id),
        checksum=checksum[:12],
        rows=len(resolved),
    )
    return {
        "source_file_checksum": checksum,
        "filename": file.filename,
        "sheets": parsed["sheets"],
        "summary": _summarise(resolved),
        "rows": [_as_json(r) for r in resolved],
    }


@router.post("/commit")
async def commit_historical_import(
    file: UploadFile = File(...),
    confirm_checksum: str = Form(...),
    kind: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Write the importable rows in one transaction.

    confirm_checksum must match the file, which is what stops a commit landing on
    a different workbook than the one reviewed in the preview.
    """
    wb, checksum, _ = await _read_upload(file, kind)
    if confirm_checksum.strip() != checksum:
        raise ValidationError(
            "This file does not match the one that was previewed. Preview it again before importing."
        )

    parsed = parse_workbook(wb, checksum)
    resolved = (await _resolve(db, parsed["rows"], checksum))["resolved"]
    ready = [r for r in resolved if r["importable"]]

    batch = f"hist-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    now = datetime.now(timezone.utc)
    demos_made = follow_ups_made = 0

    for entry in ready:
        row: ActivityRow = entry["row"]
        if row.activity_type == ACTIVITY_DEMO:
            await db.execute(text("""
                insert into demos
                  (id, contact_id, company_id, owner_id, stage, status, summary, notes,
                   next_step, is_historical, historical_source, historical_date,
                   source_sheet, source_row, import_key, source_file_checksum,
                   created_by_id, created_at, updated_at)
                values
                  (gen_random_uuid(), :contact_id, :company_id, :owner_id, 'HISTORICAL',
                   :status, :summary, :notes, :next_step, true, :source, :hist_date,
                   :sheet, :row, :key, :checksum, :actor, :now, :now)
                on conflict (import_key) where import_key is not null do nothing
            """), {
                "contact_id": entry["contact_id"], "company_id": entry["company_id"],
                "owner_id": entry["owner_id"], "status": (row.outcome or "COMPLETED")[:50],
                "summary": row.outcome or None, "notes": row.notes or None,
                "next_step": row.next_step or None, "source": f"{batch}:{row.sheet}",
                # Null when the sheet gave no date. Never today's date.
                "hist_date": row.activity_date, "sheet": row.sheet, "row": row.source_row,
                "key": entry["import_key"], "checksum": checksum,
                "actor": str(current_user.id), "now": now,
            })
            demos_made += 1
        else:
            await db.execute(text("""
                insert into follow_ups
                  (id, contact_id, company_id, user_id, type, status, due_at, completed_at,
                   notes, next_step, source_sheet, source_row, import_key,
                   source_file_checksum, created_at, updated_at)
                values
                  (gen_random_uuid(), :contact_id, :company_id, :user_id, 'HISTORICAL',
                   :status, :due_at, :completed_at, :notes, :next_step, :sheet, :row,
                   :key, :checksum, :now, :now)
                on conflict (import_key) where import_key is not null do nothing
            """), {
                "contact_id": entry["contact_id"], "company_id": entry["company_id"],
                "user_id": entry["owner_id"], "status": (row.outcome or "COMPLETED")[:50],
                "due_at": row.activity_date, "completed_at": row.activity_date,
                "notes": row.notes or row.outcome or None, "next_step": row.next_step or None,
                "sheet": row.sheet, "row": row.source_row, "key": entry["import_key"],
                "checksum": checksum, "now": now,
            })
            follow_ups_made += 1

    logger.info(
        "historical_import.committed",
        user_id=str(current_user.id), checksum=checksum[:12], batch=batch,
        demos=demos_made, follow_ups=follow_ups_made,
    )
    return {
        "batch_id": batch,
        "source_file_checksum": checksum,
        "summary": _summarise(resolved),
        "imported": {"demos": demos_made, "follow_ups": follow_ups_made,
                     "total": demos_made + follow_ups_made},
        "skipped": [_as_json(r) for r in resolved if not r["importable"]],
    }
