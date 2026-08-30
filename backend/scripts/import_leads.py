"""
import_leads.py — Idempotent real leads importer for Alpha Pro MENA CRM.

Reads gulf_leads_source.xlsx (10 sheets with inconsistent structures),
de-duplicates by email then by (name+phone), maps salesperson names to real
user accounts, and upserts Contact records via import_key for safe re-runs.

Usage (from the backend/ directory):
    python -m app.import_leads

Or with a custom file path:
    LEADS_XLSX_PATH=../data/my_file.xlsx python -m app.import_leads

Requirements:
    pip install openpyxl

Output:
    Prints a summary table: sheets processed, rows read, duplicates merged,
    new contacts inserted, rows skipped (already in DB), warnings.
"""
import asyncio
import hashlib
import os
import re
import sys
import uuid as _uuid_mod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

# Default path: repo_root/data/gulf_leads_source.xlsx
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/app/import_leads.py → repo root
DEFAULT_XLSX_PATH = _REPO_ROOT / "data" / "gulf_leads_source.xlsx"
XLSX_PATH = Path(os.environ.get("LEADS_XLSX_PATH", str(DEFAULT_XLSX_PATH)))

# Salesperson first-name → email mapping (case-insensitive, partial match)
SALESPERSON_EMAILS = {
    "saleh":  "saleh@alphapromena.com",
    "hassan": "hassan@alphapromena.com",
    "amin":   "amin@alphapromena.com",
    "ghaida": "ghaida@alphapromena.com",
    "ghayda": "ghaida@alphapromena.com",   # common alternate spelling
    "قسي":    "qusai@alphapromena.com",
    "qusai":  "qusai@alphapromena.com",
}

# Sheets that contain contacts (not just meta/index sheets)
CONTACT_SHEETS = {
    "Leads": "primary",       # ~3,950 rows — canonical source
    "Ghaida fu": "ghaida",    # per-salesperson follow-up
    "Amin fu":   "amin",      # per-salesperson follow-up
    "Qusai":     "qusai",     # per-salesperson / country
    "Oman":      "oman",      # per-country
    "Oman Leads":"oman",
    "Oman L.S":  "oman",
    "Oman Amin": "amin",
    "Demo":      "demo",      # demo tracking
}

# Columns we skip — purely meta/index sheets
SKIP_SHEETS = {"Companies"}


# ── Row representation ────────────────────────────────────────────────────────

@dataclass
class LeadRow:
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    position: str = ""
    phone: str = ""
    email: str = ""
    notes: str = ""
    salesperson: str = ""   # raw value from column
    attempt_count: int = 0
    last_contacted: Optional[str] = None
    status_hint: str = "NEW"  # inferred from sheet context
    source_sheet: str = ""
    import_key: str = ""       # computed SHA-256 dedup key
    # Raw text values of each attempt column — used to create Call records
    attempt_1_text: str = ""
    attempt_2_text: str = ""
    attempt_3_text: str = ""


# ── Normalization helpers ─────────────────────────────────────────────────────

def _norm_email(raw: str) -> str:
    if not raw:
        return ""
    return str(raw).strip().lower()


def _norm_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"[^\d+]", "", str(raw).strip())
    # Normalise Gulf numbers: 05x → +9665x, 09x → +9689x (Oman), etc.
    if digits.startswith("05") and len(digits) == 10:
        digits = "+966" + digits[1:]
    elif digits.startswith("9665") and len(digits) == 12:
        digits = "+" + digits
    return digits


def _make_import_key(row: LeadRow) -> str:
    """Stable dedup key: prefer email, fall back to name+phone, fall back to name+company."""
    if row.email:
        raw = f"email:{row.email.lower().strip()}"
    elif row.phone:
        raw = f"phone:{_norm_phone(row.phone)}:{row.first_name.strip().lower()}"
    else:
        raw = f"name:{row.first_name.strip().lower()}:{row.last_name.strip().lower()}:{row.company.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _split_name(full: str) -> Tuple[str, str]:
    """Split 'First Last' into (first, last). Handles Arabic names."""
    full = full.strip()
    if not full:
        return ("", "")
    parts = full.rsplit(" ", 1)
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], parts[1])


def _parse_attempts(val) -> int:
    """Parse attempt count from a cell value (may be numeric, text, or empty)."""
    if val is None:
        return 0
    try:
        n = int(float(str(val)))
        return max(0, n)
    except (ValueError, TypeError):
        return 0


def _cell_str(val) -> str:
    """Convert any openpyxl cell value to a clean string."""
    if val is None:
        return ""
    return str(val).strip()


# ── Header detection ──────────────────────────────────────────────────────────

# Known header keywords (case-insensitive) — if a cell contains any of these,
# that row is likely the real header row.
HEADER_KEYWORDS = {
    "company", "companies", "phone", "mobile", "email", "name", "position",
    "title", "sales", "attempt", "notes", "country", "last", "first",
    "الشركة", "الهاتف", "الاسم", "المنصب", "المبيعات", "محاولة",
}

def _looks_like_header(row_values: List) -> bool:
    """Return True if a majority of non-empty cells look like column header labels."""
    non_empty = [v for v in row_values if v is not None and str(v).strip()]
    if not non_empty:
        return False
    matches = sum(
        1 for v in non_empty
        if any(kw in str(v).strip().lower() for kw in HEADER_KEYWORDS)
    )
    return matches >= max(1, len(non_empty) // 3)


def _detect_header_row(sheet) -> Tuple[int, Dict[str, int]]:
    """
    Scan the first 5 rows to find the real header row.
    Returns (header_row_idx_0based, {col_name_lower: col_idx_0based}).
    """
    for row_idx in range(min(5, sheet.max_row)):
        values = [sheet.cell(row=row_idx + 1, column=c + 1).value for c in range(sheet.max_column)]
        if _looks_like_header(values):
            col_map = {}
            for c_idx, v in enumerate(values):
                if v is not None:
                    col_map[str(v).strip().lower()] = c_idx
            return row_idx, col_map
    # Fallback: treat row 0 as header regardless
    values = [sheet.cell(row=1, column=c + 1).value for c in range(sheet.max_column)]
    col_map = {str(v).strip().lower(): c for c, v in enumerate(values) if v is not None}
    return 0, col_map


# ── Column name aliases ───────────────────────────────────────────────────────

def _find_col(col_map: Dict[str, int], *aliases) -> Optional[int]:
    """Find column index matching any of the given alias strings (case-insensitive partial match)."""
    for alias in aliases:
        al = alias.lower()
        # Exact match first
        if al in col_map:
            return col_map[al]
        # Partial match
        for key, idx in col_map.items():
            if al in key or key in al:
                return idx
    return None


# ── Sheet parser ──────────────────────────────────────────────────────────────

def _parse_sheet(sheet, sheet_name: str, default_salesperson: str = "") -> List[LeadRow]:
    """Parse a single worksheet into a list of LeadRow objects."""
    header_row_idx, col_map = _detect_header_row(sheet)
    data_start = header_row_idx + 2  # 1-indexed, after header

    # Map semantic fields to column indices
    col_first   = _find_col(col_map, "first name", "first", "name", "الاسم الأول", "الاسم")
    col_last    = _find_col(col_map, "last name", "last", "اسم العائلة")
    col_full    = _find_col(col_map, "full name", "الاسم الكامل")
    col_company = _find_col(col_map, "company", "companies", "الشركة", "company name")
    col_pos     = _find_col(col_map, "position", "title", "job title", "المنصب", "الوظيفة")
    col_phone   = _find_col(col_map, "phone", "mobile", "phone number", "الهاتف", "الجوال", "رقم الهاتف")
    col_email   = _find_col(col_map, "email", "e-mail", "البريد الإلكتروني")
    col_sales   = _find_col(col_map, "sales person", "salesperson", "sales", "مندوب", "assigned")
    col_notes   = _find_col(col_map, "notes", "note", "ملاحظات", "تعليق")
    col_att1    = _find_col(col_map, "1st attempt", "1st attempts", "attempt 1", "المحاولة الأولى")
    col_att2    = _find_col(col_map, "2nd attempt", "2nd attempts", "attempt 2")
    col_att3    = _find_col(col_map, "3rd attempt", "3rd attempts", "attempt 3")
    col_last_ct = _find_col(col_map, "last time contacted", "last contact", "last contacted", "آخر تواصل")

    rows: List[LeadRow] = []

    for row_num in range(data_start, sheet.max_row + 1):
        def get(col_idx) -> str:
            if col_idx is None:
                return ""
            return _cell_str(sheet.cell(row=row_num, column=col_idx + 1).value)

        # Name resolution: prefer separate first/last, fall back to full name split
        first_name = get(col_first)
        last_name  = get(col_last)
        if not first_name:
            full = get(col_full)
            if full:
                first_name, last_name = _split_name(full)

        # Skip completely empty rows
        if not first_name and not get(col_phone) and not get(col_email):
            continue

        # Attempt count and raw text values
        def get_cell_raw(col_idx):
            if col_idx is None:
                return ""
            return _cell_str(sheet.cell(row=row_num, column=col_idx + 1).value)

        att1_raw = get_cell_raw(col_att1)
        att2_raw = get_cell_raw(col_att2)
        att3_raw = get_cell_raw(col_att3)

        # Attempt count: if cell looks like a number, use it directly;
        # if it's text (outcome description), count it as 1 attempt.
        def count_attempt(raw: str) -> int:
            if not raw:
                return 0
            try:
                return max(0, int(float(raw)))
            except (ValueError, TypeError):
                return 1  # non-numeric text = one attempt logged

        att1 = count_attempt(att1_raw)
        att2 = count_attempt(att2_raw)
        att3 = count_attempt(att3_raw)
        attempt_count = min(att1 + att2 + att3, 3)  # cap at 3 real attempts

        # Build row
        lr = LeadRow(
            first_name=first_name,
            last_name=last_name,
            company=get(col_company),
            position=get(col_pos),
            phone=get(col_phone),
            email=_norm_email(get(col_email)),
            notes=get(col_notes),
            salesperson=get(col_sales) or default_salesperson,
            attempt_count=attempt_count,
            last_contacted=get(col_last_ct) or None,
            status_hint="DEMO_SCHEDULED" if sheet_name == "Demo" else ("NO_ANSWER" if attempt_count >= 2 else "NEW"),
            source_sheet=sheet_name,
            attempt_1_text=att1_raw,
            attempt_2_text=att2_raw,
            attempt_3_text=att3_raw,
        )
        lr.import_key = _make_import_key(lr)
        rows.append(lr)

    return rows


# ── De-duplication ────────────────────────────────────────────────────────────

def _completeness_score(lr: LeadRow) -> int:
    """Higher is better — used to pick the winner when merging duplicates."""
    score = 0
    if lr.email:       score += 10
    if lr.phone:       score += 8
    if lr.company:     score += 4
    if lr.position:    score += 3
    if lr.notes:       score += 2
    if lr.last_contacted: score += 1
    if lr.salesperson: score += 2
    return score


def _merge_rows(existing: LeadRow, incoming: LeadRow) -> LeadRow:
    """Merge two rows for the same contact, keeping the most complete data."""
    winner = existing if _completeness_score(existing) >= _completeness_score(incoming) else incoming
    loser  = incoming if winner is existing else existing

    # Fill any gaps in winner from loser
    if not winner.email     and loser.email:     winner.email     = loser.email
    if not winner.phone     and loser.phone:     winner.phone     = loser.phone
    if not winner.company   and loser.company:   winner.company   = loser.company
    if not winner.position  and loser.position:  winner.position  = loser.position
    if not winner.notes     and loser.notes:     winner.notes     = loser.notes
    if not winner.salesperson and loser.salesperson: winner.salesperson = loser.salesperson

    # Take max attempt count
    winner.attempt_count = max(winner.attempt_count, loser.attempt_count)

    # If Demo sheet contributed, upgrade status hint
    if existing.status_hint == "DEMO_SCHEDULED" or incoming.status_hint == "DEMO_SCHEDULED":
        winner.status_hint = "DEMO_SCHEDULED"

    return winner


def _dedup(all_rows: List[LeadRow]) -> Tuple[List[LeadRow], int]:
    """De-duplicate rows. Returns (unique_rows, merged_count)."""
    seen: Dict[str, LeadRow] = {}
    merged = 0

    for row in all_rows:
        key = row.import_key
        if key in seen:
            seen[key] = _merge_rows(seen[key], row)
            merged += 1
        else:
            seen[key] = row

    return list(seen.values()), merged


# ── Database insertion ────────────────────────────────────────────────────────

async def _resolve_user_ids(db) -> Dict[str, str]:
    """Return {normalized_first_name: user_id_str} for known salespersons."""
    from sqlalchemy import select
    from app.models.user import User

    known_emails = list(set(SALESPERSON_EMAILS.values()))
    result = await db.execute(select(User).where(User.email.in_(known_emails)))
    users = result.scalars().all()

    mapping: Dict[str, str] = {}
    for u in users:
        first = u.first_name.strip().lower()
        mapping[first] = str(u.id)
        # Also map by email prefix
        email_prefix = u.email.split("@")[0].lower()
        mapping[email_prefix] = str(u.id)

    return mapping


async def _insert_rows(db, rows: List[LeadRow], user_id_map: Dict[str, str]) -> Tuple[int, int, List[str]]:
    """
    Insert rows into the DB. Returns (inserted, skipped, warnings).
    Uses import_key for idempotency — skips rows already in DB.
    """
    from sqlalchemy import select
    from app.models.contact import Contact, ContactStatus
    from app.models.company import Company
    from app.core.security import normalize_email, normalize_phone

    # Pre-load existing import_keys to avoid re-inserting
    existing_keys_result = await db.execute(
        select(Contact.import_key).where(Contact.import_key.isnot(None))
    )
    existing_keys = {row[0] for row in existing_keys_result.all()}

    inserted = 0
    skipped = 0
    warnings: List[str] = []

    # Company name → id cache
    company_cache: Dict[str, str] = {}

    async def get_or_create_company(name: str) -> Optional[str]:
        if not name:
            return None
        key = name.strip().lower()
        if key in company_cache:
            return company_cache[key]
        result = await db.execute(select(Company).where(Company.name.ilike(name.strip())))
        comp = result.scalar_one_or_none()
        if not comp:
            comp = Company(name=name.strip())
            db.add(comp)
            await db.flush()
        company_cache[key] = str(comp.id)
        return company_cache[key]

    # ── Outcome normalization ─────────────────────────────────────────────────
    # Maps raw attempt text from the sheet → Call.outcome enum value.
    # Mirrors the same mapping in integrations/google_sheets/service.py.
    def _normalize_outcome(att_text: str) -> str:
        if not att_text:
            return "NO_ANSWER"
        upper = att_text.strip().upper()
        if "NOT INTERESTED" in upper or "غير مهتم" in att_text:
            return "NOT_INTERESTED"
        elif "INTERESTED" in upper or "مهتم" in att_text:
            return "INTERESTED"
        elif "EMAIL" in upper or "إيميل" in att_text or "ايميل" in att_text:
            return "EMAIL_REQUESTED"
        elif "WHATSAPP" in upper or "واتساب" in att_text:
            return "WHATSAPP_REQUESTED"
        elif "DEMO" in upper or "عرض" in att_text:
            return "DEMO_REQUESTED"
        elif "CALL LATER" in upper or "CALLBACK" in upper or "اتصال لاحق" in att_text:
            return "CALL_LATER"
        elif "BUSY" in upper or "مشغول" in att_text:
            return "BUSY"
        elif "WRONG" in upper or "رقم خاطئ" in att_text:
            return "WRONG_NUMBER"
        elif "VOICEMAIL" in upper:
            return "VOICEMAIL"
        elif "ANSWERED" in upper or "تم الرد" in att_text:
            return "ANSWERED"
        elif "NO ANSWER" in upper or upper in ("NA", "NO ANS", "N/A") or "لم يرد" in att_text:
            return "NO_ANSWER"
        else:
            # Default: treat any non-empty text as a no-answer attempt (most common sheet value)
            return "NO_ANSWER"

    # ── Sequential sheet_order ────────────────────────────────────────────────
    # Fetch current max so we don't collide with previously-imported contacts
    from sqlalchemy import func as sa_func
    max_order_result = await db.execute(
        select(sa_func.coalesce(sa_func.max(Contact.sheet_order), 0))
    )
    next_order = (max_order_result.scalar_one() or 0) + 1

    from app.models.call import Call
    from datetime import timezone

    for row in rows:
        if row.import_key in existing_keys:
            skipped += 1
            continue

        # Resolve salesperson → user_id
        owner_id = None
        sp_raw = row.salesperson.strip().lower() if row.salesperson else ""
        if sp_raw:
            owner_id = user_id_map.get(sp_raw)
            if not owner_id:
                for key, uid in user_id_map.items():
                    if key in sp_raw or sp_raw in key:
                        owner_id = uid
                        break
            if not owner_id:
                warnings.append(f"Unknown salesperson '{row.salesperson}' for {row.first_name} {row.last_name} — left unassigned")

        company_id = await get_or_create_company(row.company)

        status = ContactStatus.NEW
        if row.status_hint == "DEMO_SCHEDULED":
            status = ContactStatus.DEMO_SCHEDULED
        elif row.status_hint == "NO_ANSWER" or row.attempt_count >= 2:
            status = ContactStatus.NO_ANSWER
        elif row.attempt_count == 1:
            status = ContactStatus.CONTACTED

        email_norm = normalize_email(row.email) if row.email else None
        phone_norm = normalize_phone(row.phone) if row.phone else None

        contact = Contact(
            first_name=row.first_name or "Unknown",
            last_name=row.last_name or None,
            company_id=company_id,
            position=row.position or None,
            email=row.email or None,
            normalized_email=email_norm,
            phone=row.phone or None,
            normalized_phone=phone_norm,
            notes=row.notes or None,
            owner_id=owner_id,
            status=status,
            attempt_count=row.attempt_count,
            source=f"Excel Import ({row.source_sheet})",
            import_key=row.import_key,
            sheet_order=next_order,
        )
        db.add(contact)
        await db.flush()  # flush now so contact.id exists for Call FK
        next_order += 1

        # Create one Call record per non-empty attempt column.
        # This is the KEY fix: previously only Contact.attempt_count was stored,
        # giving the funnel no Call rows to count, causing impossible ratios.
        for att_num, att_text in [(1, row.attempt_1_text), (2, row.attempt_2_text), (3, row.attempt_3_text)]:
            if not att_text:
                continue
            call_record = Call(
                contact_id=contact.id,
                user_id=uuid.UUID(owner_id) if owner_id else None,
                outcome=_normalize_outcome(att_text),
                attempt_number=att_num,
                duration_seconds=0,
                notes=f"Historical attempt {att_num} (imported from {row.source_sheet}): {att_text}",
                called_at=datetime.now(timezone.utc),
            )
            db.add(call_record)

        existing_keys.add(row.import_key)
        inserted += 1

    await db.flush()
    return inserted, skipped, warnings



# ── Main entry point ──────────────────────────────────────────────────────────

async def run_import():
    try:
        import openpyxl
    except ImportError:
        print("ERROR: openpyxl is required. Run: pip install openpyxl")
        sys.exit(1)

    if not XLSX_PATH.exists():
        print(f"\nERROR: Excel file not found at: {XLSX_PATH}")
        print(f"Please place the file at: {XLSX_PATH}")
        print("Or set the LEADS_XLSX_PATH environment variable to the correct path.\n")
        sys.exit(1)

    print(f"\nReading: {XLSX_PATH}")
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)

    print(f"Sheets found: {wb.sheetnames}")

    all_rows: List[LeadRow] = []
    sheet_stats: Dict[str, int] = {}

    for sheet_name in wb.sheetnames:
        if sheet_name in SKIP_SHEETS:
            print(f"  Skipping meta sheet: {sheet_name}")
            continue

        if sheet_name not in CONTACT_SHEETS:
            print(f"  Skipping unknown sheet: {sheet_name}")
            continue

        ws = wb[sheet_name]
        default_sp = CONTACT_SHEETS[sheet_name] if CONTACT_SHEETS[sheet_name] not in ("primary", "demo", "oman") else ""
        rows = _parse_sheet(ws, sheet_name, default_salesperson=default_sp)
        sheet_stats[sheet_name] = len(rows)
        all_rows.extend(rows)
        print(f"  Sheet '{sheet_name}': {len(rows)} rows parsed")

    total_raw = len(all_rows)
    deduped_rows, merged_count = _dedup(all_rows)
    print(f"\nTotal raw rows: {total_raw}")
    print(f"After de-duplication: {len(deduped_rows)} unique contacts ({merged_count} merges)")

    # Insert into database
    from app.database import AsyncSessionLocal, engine, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        user_id_map = await _resolve_user_ids(db)
        print(f"\nResolved {len(user_id_map)} salesperson→user mappings: {list(user_id_map.keys())}")

        inserted, skipped, warnings = await _insert_rows(db, deduped_rows, user_id_map)
        await db.commit()

    # Summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"  Sheets processed     : {len(sheet_stats)}")
    for sheet, count in sheet_stats.items():
        print(f"    {sheet:<20}: {count} rows")
    print(f"  Total raw rows       : {total_raw}")
    print(f"  Duplicates merged    : {merged_count}")
    print(f"  Unique contacts      : {len(deduped_rows)}")
    print(f"  Inserted (new)       : {inserted}")
    print(f"  Skipped (already in DB): {skipped}")
    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings[:20]:
            print(f"    ⚠ {w}")
        if len(warnings) > 20:
            print(f"    ... and {len(warnings) - 20} more")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_import())
