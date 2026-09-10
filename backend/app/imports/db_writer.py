"""
app.imports.db_writer — Async DB interactions for the import pipeline.

Responsibilities
----------------
- load_db_snapshot(db): query ALL active contacts (including those without
  import_key) and return a DbSnapshot for reconciliation.
- resolve_salesperson_map(db): map salesperson first-names to real User UUIDs.
  Aseel is explicitly excluded from the import owner pool — importing contacts
  must not make Aseel the owner of every record she uploads.
- get_or_create_company(db, name, cache): ilike exact match before creating.
- upsert_contact(db, row, existing_id, owner_id, company_id, ...): idempotent
  insert-or-update. Preserves DNC, existing notes, calls, history, and manual
  ownership corrections.
- run_import(db, rows, dry_run): orchestrate full batch.
"""
from __future__ import annotations

import uuid as _uuid_mod
from datetime import datetime, timezone
from typing import Dict, FrozenSet, List, Optional, Tuple

import structlog
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.imports.normalizers import normalize_email, normalize_phone
from app.imports.reconciler import (
    KNOWN_SALESPERSON_NAMES,
    LEGACY_SALESPERSON_NAMES,
    DbSnapshot,
    ImportReport,
    classify_rows,
    deduplicate,
)
from app.imports.workbook_reader import LeadRow
from app.models.contact import Contact, ContactPriority, ContactStatus
from app.models.company import Company
from app.models.user import User

logger = structlog.get_logger(__name__)

# Authoritative first-name → email map for salesperson resolution
_SALESPERSON_EMAILS: Dict[str, str] = {
    "saleh":   "saleh@alphapromena.com",
    "hassan":  "hassan@alphapromena.com",
    "amin":    "amin@alphapromena.com",
    "ghaida":  "ghaida@alphapromena.com",
    "ghayda":  "ghaida@alphapromena.com",
    "qusai":   "qusai@alphapromena.com",
    # abdallah is a manager — can own contacts but is not a salesperson in imports
}

# Users who must NEVER be assigned as import owners (they are data operators, not salespeople)
_IMPORT_OWNER_EXCLUDE_EMAILS: FrozenSet[str] = frozenset({"aseel@alphapromena.com"})


# ── DB snapshot (for matching legacy contacts) ────────────────────────────────

async def load_db_snapshot(db: AsyncSession) -> DbSnapshot:
    """Load all active contacts into a DbSnapshot for reconciliation.

    Includes contacts without import_key so that legacy records entered
    before import_key existed can still be matched by phone or email.
    """
    snap = DbSnapshot()

    result = await db.execute(
        select(
            Contact.id,
            Contact.import_key,
            Contact.normalized_email,
            Contact.normalized_phone,
            Contact.first_name,
            Contact.owner_id,
            Contact.status,
        ).where(Contact.deleted_at.is_(None))
    )
    for row in result.all():
        cid, key, ne, np_, first, owner_id, status = row

        if key:
            snap.key_to_id[key]   = cid
            snap.key_to_owner[key] = (owner_id, str(status))
        if ne:
            snap.email_to_id[ne] = cid
        if np_:
            # Only keep the first entry per phone to avoid shared-office collisions
            if np_ not in snap.phone_to_id:
                snap.phone_to_id[np_] = (cid, first or "")

    return snap


# ── Salesperson resolver ──────────────────────────────────────────────────────

async def resolve_salesperson_map(db: AsyncSession) -> Dict[str, _uuid_mod.UUID]:
    """Return {salesperson_name_lower: user_uuid} for allowed import owners.

    Aseel and other non-salesperson roles are excluded — importing contacts
    must not make the uploading user the owner of every contact.
    """
    emails = [e for e in _SALESPERSON_EMAILS.values()
              if e not in _IMPORT_OWNER_EXCLUDE_EMAILS]
    emails = list(set(emails))

    result = await db.execute(
        select(User).where(
            User.email.in_(emails),
            User.deleted_at.is_(None),
        )
    )
    users = result.scalars().all()

    mapping: Dict[str, _uuid_mod.UUID] = {}
    for u in users:
        first = u.first_name.strip().lower()
        prefix = u.email.split("@")[0].lower()
        mapping[first]  = u.id
        mapping[prefix] = u.id

    if "ghaida" in mapping:
        mapping["ghayda"] = mapping["ghaida"]

    return mapping


def _resolve_owner(
    salesperson_raw: str,
    sp_map: Dict[str, _uuid_mod.UUID],
    row: LeadRow,
) -> Optional[_uuid_mod.UUID]:
    """Map a raw salesperson string to a CRM user UUID.

    Returns None for blank, unknown, or legacy (Maria/Raneem) names.
    """
    sp_lower = salesperson_raw.strip().lower() if salesperson_raw else ""
    if not sp_lower:
        return None
    if sp_lower in sp_map:
        return sp_map[sp_lower]
    # Partial match
    for key, uid in sp_map.items():
        if key in sp_lower or sp_lower in key:
            return uid
    if sp_lower not in LEGACY_SALESPERSON_NAMES:
        logger.warning(
            "import.unknown_salesperson",
            salesperson=salesperson_raw,
            sheet=row.source_sheet,
            row=row.source_row,
        )
    return None


# ── Company helper ────────────────────────────────────────────────────────────

async def get_or_create_company(
    db: AsyncSession,
    name: str,
    cache: Dict[str, _uuid_mod.UUID],
) -> Optional[_uuid_mod.UUID]:
    """Return a company UUID, creating the record only if truly absent.

    Uses case-insensitive exact match (ilike) before inserting.
    Returns None for blank names.
    """
    if not name or not name.strip():
        return None
    name = name.strip()
    key  = name.lower()
    if key in cache:
        return cache[key]

    result = await db.execute(
        select(Company).where(
            Company.name.ilike(name),
            Company.deleted_at.is_(None),
        )
    )
    co = result.scalar_one_or_none()
    if not co:
        co = Company(name=name)
        db.add(co)
        await db.flush()
        logger.debug("import.company_created", name=name)

    cache[key] = co.id
    return co.id


# ── Outcome normaliser for historical calls ───────────────────────────────────

def _norm_outcome(att_text: str) -> str:
    if not att_text:
        return "NO_ANSWER"
    u = att_text.strip().upper()
    if "NOT INTERESTED" in u:           return "NOT_INTERESTED"
    if "INTERESTED"     in u:           return "INTERESTED"
    if "EMAIL"          in u:           return "EMAIL_REQUESTED"
    if "WHATSAPP"       in u:           return "WHATSAPP_REQUESTED"
    if "DEMO"           in u:           return "DEMO_REQUESTED"
    if "CALL LATER"     in u or "CALLBACK" in u: return "CALL_LATER"
    if "BUSY"           in u:           return "BUSY"
    if "WRONG"          in u:           return "WRONG_NUMBER"
    if "VOICEMAIL"      in u:           return "VOICEMAIL"
    if "ANSWERED"       in u:           return "ANSWERED"
    return "NO_ANSWER"


# ── Single contact upsert ─────────────────────────────────────────────────────

async def upsert_contact(
    db: AsyncSession,
    row: LeadRow,
    existing_id: Optional[object],
    owner_id: Optional[_uuid_mod.UUID],
    company_id: Optional[_uuid_mod.UUID],
    next_sheet_order: int,
    dry_run: bool = False,
) -> Tuple[str, int]:
    """Insert or update one Contact, returning ("inserted"|"updated"|"skipped", next_order).

    Idempotency rules:
    - If existing_id is set: enrich blank fields only.  Never overwrite non-blank
      CRM values with spreadsheet blanks.  Never touch DNC contacts.
    - If existing_id is None: insert a new Contact.
    - Owner: only set if currently unassigned. Never reassign an already-owned contact.
    - Status: never downgrade a more-advanced status to a lower one.
    - dry_run: calculate action without any write.
    """
    from app.models.call import Call

    if dry_run:
        return ("would_update" if existing_id else "would_insert", next_sheet_order)

    # ── UPDATE ────────────────────────────────────────────────────────────
    if existing_id is not None:
        result = await db.execute(
            select(Contact).where(
                Contact.id == existing_id,
                Contact.deleted_at.is_(None),
            )
        )
        contact = result.scalar_one_or_none()
        if not contact:
            return ("skipped", next_sheet_order)

        # Never touch DNC contacts
        if contact.is_dnc:
            return ("skipped", next_sheet_order)

        changed = False
        # Fill only truly blank fields
        if not contact.email and row.email:
            contact.email = row.email
            contact.normalized_email = row.normalized_email
            changed = True
        if not contact.phone and row.phone:
            contact.phone = row.phone
            contact.normalized_phone = row.normalized_phone
            changed = True
        if not contact.company_id and company_id:
            contact.company_id = company_id
            changed = True
        if not contact.position and row.position:
            contact.position = row.position
            changed = True
        if not contact.notes and row.notes:
            contact.notes = row.notes
            changed = True
        # Only assign owner if currently unassigned
        if not contact.owner_id and owner_id:
            contact.owner_id = owner_id
            changed = True
        # Stamp import_key if missing (legacy contacts)
        if not contact.import_key and row.import_key:
            contact.import_key = row.import_key
            changed = True

        if changed:
            db.add(contact)
            await db.flush()
            return ("updated", next_sheet_order)
        return ("skipped", next_sheet_order)

    # ── INSERT ────────────────────────────────────────────────────────────
    status_map = {
        "DEMO_SCHEDULED": ContactStatus.DEMO_SCHEDULED,
        "UNASSIGNED":     ContactStatus.UNASSIGNED,
        "NO_ANSWER":      ContactStatus.NO_ANSWER,
        "CONTACTED":      ContactStatus.CONTACTED,
    }
    new_status = status_map.get(row.status_hint, ContactStatus.NEW)

    contact = Contact(
        first_name=row.first_name or "Unknown",
        last_name=row.last_name or None,
        company_id=company_id,
        position=row.position or None,
        email=row.email or None,
        normalized_email=row.normalized_email or None,
        phone=row.phone or None,
        normalized_phone=row.normalized_phone or None,
        notes=row.notes or None,
        owner_id=owner_id,
        status=new_status,
        priority=ContactPriority.MEDIUM,
        attempt_count=row.attempt_count,
        source=f"Excel Import ({row.source_sheet})",
        import_key=row.import_key,
        sheet_order=next_sheet_order,
        source_sheet=row.source_sheet,
    )
    db.add(contact)
    await db.flush()

    # Historical call records for attempt columns
    for att_num, att_text in [(1, row.attempt_1_text), (2, row.attempt_2_text), (3, row.attempt_3_text)]:
        if not att_text:
            continue
        call = Call(
            contact_id=contact.id,
            user_id=owner_id,
            outcome=_norm_outcome(att_text),
            attempt_number=att_num,
            duration_seconds=0,
            notes=f"Historical attempt {att_num} (from {row.source_sheet}): {att_text}",
            called_at=datetime.now(timezone.utc),
        )
        db.add(call)

    return ("inserted", next_sheet_order + 1)


# ── Batch orchestrator ────────────────────────────────────────────────────────

async def run_import(
    db: AsyncSession,
    all_rows: List[LeadRow],
    dry_run: bool = False,
) -> ImportReport:
    """Orchestrate a full import: dedup → load snapshot → classify → upsert.

    Idempotent: running twice with identical data produces identical results.
    """
    report = ImportReport()

    # ── Step 1: Intra-batch dedup ─────────────────────────────────────────
    unique_rows, intra_dups = deduplicate(all_rows)
    report.total_intra_duplicates = intra_dups

    # ── Step 2: Load DB snapshot (all contacts incl. legacy without key) ──
    snap = await load_db_snapshot(db)

    # ── Step 3: Classify ──────────────────────────────────────────────────
    to_upsert, _to_skip = classify_rows(unique_rows, snap, report)

    if dry_run:
        return report

    # ── Step 4: Resolve salesperson map ──────────────────────────────────
    sp_map = await resolve_salesperson_map(db)

    # ── Step 5: Starting sheet_order ─────────────────────────────────────
    max_ord = await db.execute(
        select(sa_func.coalesce(sa_func.max(Contact.sheet_order), 0))
    )
    next_order = (max_ord.scalar_one() or 0) + 1

    # ── Step 6: Company cache ─────────────────────────────────────────────
    company_cache: Dict[str, _uuid_mod.UUID] = {}

    # ── Step 7: Upsert ────────────────────────────────────────────────────
    for i, (row, existing_id) in enumerate(to_upsert):
        try:
            owner_id   = _resolve_owner(row.salesperson, sp_map, row)
            company_id = await get_or_create_company(db, row.company, company_cache)

            async with db.begin_nested():
                action, next_order = await upsert_contact(
                    db, row, existing_id, owner_id, company_id, next_order, dry_run=False
                )
                if action == "inserted":
                    report.total_inserted += 1
                elif action == "updated":
                    report.total_updated += 1
                else:
                    report.total_skipped += 1

        except Exception as exc:
            report.total_errors += 1
            logger.error(
                "import.row_error",
                sheet=row.source_sheet, row=row.source_row, error=str(exc),
            )

        if i > 0 and i % 250 == 0:
            await db.flush()

    await db.flush()
    return report
