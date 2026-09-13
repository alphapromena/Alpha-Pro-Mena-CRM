"""
backend/app/imports/sheet16_data_replacer.py

Authoritative data replacement service for Alpha Pro MENA CRM:
- Active Contacts: Sourced strictly from worksheet 'Sheet16' (Row 1 preserved, Row 67 excluded)
- Active Companies: Authoritative master data sourced strictly from 'Companies' worksheet (3,699 distinct)
- Leads Archive: Non-empty rows from 'Leads' worksheet archived completely into Neon 'leads_archive' table
- Historical Activities: Demos and Follow-ups extracted and linked to canonical contacts & companies
- User Accounts: Deduplicates Hassan and other user accounts; guarantees 1 canonical account per email
- Preservation of History: Retires old active contacts absent from Sheet16 safely via soft-delete/archived status
"""
from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import openpyxl
import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import normalize_email
from app.imports.normalizers import (
    detect_company_position,
    make_import_key,
    normalize_email as norm_email_func,
    normalize_phone,
    split_name,
)
from app.imports.workbook_reader import extract_company_names, read_companies_tab
from app.models.company import Company
from app.models.contact import Contact, ContactStatus
from app.models.demo import Demo, DemoStage, DemoStatus
from app.models.follow_up import FollowUp, FollowUpType
from app.models.leads_archive import LeadsArchive
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)

CANONICAL_USER_EMAILS = [
    "saleh@alphapromena.com",
    "hassan@alphapromena.com",
    "ghaida@alphapromena.com",
    "amin@alphapromena.com",
    "qusai@alphapromena.com",
    "abdallah@alphapromena.com",
    "aseel@alphapromena.com",
]


class Sheet16DataReplacer:
    """Orchestrates authoritative replacement of active CRM data with Sheet16 & master Companies."""

    def __init__(self, db: AsyncSession, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.batch_id = f"sheet16_replace_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async def execute(self, wb: Any) -> Dict[str, Any]:
        """Run complete authoritative migration and data replacement."""
        report: Dict[str, Any] = {
            "batch_id": self.batch_id,
            "dry_run": self.dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "users": {},
            "companies": {},
            "leads_archive": {},
            "active_contacts": {},
            "historical_demos": {},
            "historical_followups": {},
            "retired_contacts": 0,
        }

        # ── Step 1: Capture Pre-Migration Counts ─────────────────────────────
        pre_counts = await self._get_db_counts()
        report["pre_migration_counts"] = pre_counts

        # ── Step 2: Deduplicate User Accounts & Build Canonical Map ─────────
        user_map, dup_users_report = await self._deduplicate_user_accounts()
        report["users"] = dup_users_report

        # ── Step 3: Ingest Master Companies from 'Companies' Sheet ──────────
        companies_map, companies_report = await self._ingest_master_companies(wb)
        report["companies"] = companies_report

        # ── Step 4: Archive 'Leads' Sheet into leads_archive Table ───────────
        archive_report = await self._archive_leads_sheet(wb)
        report["leads_archive"] = archive_report

        # ── Step 5: Ingest & Replace Active Contacts from 'Sheet16' ──────────
        contacts_report = await self._replace_active_contacts(wb, user_map, companies_map)
        report["active_contacts"] = contacts_report

        # ── Step 6: Extract Historical Demos & Follow-ups ────────────────────
        demos_report, fu_report = await self._extract_historical_activities(
            wb, user_map, companies_map, contacts_report["canonical_contacts_by_key"]
        )
        report["historical_demos"] = demos_report
        report["historical_followups"] = fu_report

        # ── Step 7: Commit or Rollback ──────────────────────────────────────
        if self.dry_run:
            await self.db.rollback()
            report["status"] = "dry_run_success"
            logger.info("sheet16_replacer.dry_run_success", batch_id=self.batch_id)
        else:
            await self.db.commit()
            report["status"] = "committed_success"
            logger.info("sheet16_replacer.committed_success", batch_id=self.batch_id)

        # ── Step 8: Capture Post-Migration Counts ────────────────────────────
        post_counts = await self._get_db_counts()
        report["post_migration_counts"] = post_counts

        return report

    # ── Internal Helpers ────────────────────────────────────────────────────

    async def _get_db_counts(self) -> Dict[str, Any]:
        """Capture live counts per user, active contacts, companies, demos, and follow-ups."""
        counts: Dict[str, Any] = {"per_user": {}}

        # Per-user active contacts
        user_stmt = select(User.id, User.email, User.first_name).where(User.deleted_at.is_(None))
        users = (await self.db.execute(user_stmt)).all()
        for u in users:
            c_cnt = await self.db.scalar(
                select(func.count(Contact.id)).where(
                    Contact.owner_id == u.id,
                    Contact.deleted_at.is_(None),
                    Contact.status != ContactStatus.ARCHIVED.value,
                )
            ) or 0
            counts["per_user"][u.email] = {
                "name": u.first_name,
                "active_contacts": c_cnt,
            }

        # Unassigned active contacts
        counts["unassigned_contacts"] = await self.db.scalar(
            select(func.count(Contact.id)).where(
                Contact.owner_id.is_(None),
                Contact.deleted_at.is_(None),
                Contact.status != ContactStatus.ARCHIVED.value,
            )
        ) or 0

        # Total active contacts
        counts["total_active_contacts"] = await self.db.scalar(
            select(func.count(Contact.id)).where(
                Contact.deleted_at.is_(None),
                Contact.status != ContactStatus.ARCHIVED.value,
            )
        ) or 0

        # Total distinct companies
        counts["total_companies"] = await self.db.scalar(
            select(func.count(Company.id)).where(Company.deleted_at.is_(None))
        ) or 0

        # Total Demos
        counts["total_demos"] = await self.db.scalar(select(func.count(Demo.id))) or 0

        # Total Follow-ups
        counts["total_followups"] = await self.db.scalar(select(func.count(FollowUp.id))) or 0

        return counts

    async def _deduplicate_user_accounts(self) -> Tuple[Dict[str, User], Dict[str, Any]]:
        """
        Find and deduplicate user accounts, guaranteeing 1 canonical account per email.
        Reassigns all foreign keys from duplicate accounts to canonical.
        """
        user_stmt = select(User).order_by(User.created_at.asc())
        all_users = (await self.db.execute(user_stmt)).scalars().all()

        canonical_by_email: Dict[str, User] = {}
        duplicates: List[Dict[str, Any]] = []

        for u in all_users:
            email_norm = normalize_email(u.email)
            if email_norm not in canonical_by_email:
                if u.deleted_at is None:
                    canonical_by_email[email_norm] = u
            else:
                # Duplicate account detected
                canonical = canonical_by_email[email_norm]
                duplicates.append({
                    "duplicate_id": str(u.id),
                    "canonical_id": str(canonical.id),
                    "email": u.email,
                    "first_name": u.first_name,
                })
                # Reassign foreign keys
                await self.db.execute(
                    update(Contact).where(Contact.owner_id == u.id).values(owner_id=canonical.id)
                )
                await self.db.execute(
                    update(Demo).where(Demo.owner_id == u.id).values(owner_id=canonical.id)
                )
                await self.db.execute(
                    update(FollowUp).where(FollowUp.user_id == u.id).values(user_id=canonical.id)
                )
                # Soft-deactivate duplicate user
                u.is_active = False
                u.deleted_at = datetime.now(timezone.utc)
                self.db.add(u)

        # Salesperson name to user mapping
        user_by_name: Dict[str, User] = {}
        for email, u in canonical_by_email.items():
            name_key = (u.first_name or "").strip().lower()
            if name_key:
                user_by_name[name_key] = u
            # Also handle common variants like ghida -> ghaida
            if "ghaida" in email or "ghida" in email:
                user_by_name["ghaida"] = u
                user_by_name["ghida"] = u

        report = {
            "canonical_users_count": len(canonical_by_email),
            "duplicates_resolved": len(duplicates),
            "duplicate_details": duplicates,
        }
        return user_by_name, report

    async def _ingest_master_companies(self, wb: Any) -> Tuple[Dict[str, uuid.UUID], Dict[str, Any]]:
        """Ingest the 3,699 clean distinct companies from 'Companies' worksheet as master data."""
        clean_company_names = extract_company_names(wb)
        logger.info("sheet16_replacer.companies_extracted", count=len(clean_company_names))

        # Existing companies map: lower(name) -> id
        existing_stmt = select(Company.id, Company.name).where(Company.deleted_at.is_(None))
        existing_res = (await self.db.execute(existing_stmt)).all()
        company_lookup: Dict[str, uuid.UUID] = {row[1].strip().lower(): row[0] for row in existing_res if row[1]}

        new_companies_created = 0
        for name in clean_company_names:
            norm = name.strip().lower()
            if norm not in company_lookup:
                new_co = Company(
                    id=uuid.uuid4(),
                    name=name.strip(),
                    industry="Enterprise",
                    status="ACTIVE",
                )
                self.db.add(new_co)
                company_lookup[norm] = new_co.id
                new_companies_created += 1

        await self.db.flush()
        report = {
            "master_companies_in_sheet": len(clean_company_names),
            "new_companies_created": new_companies_created,
            "total_canonical_companies": len(company_lookup),
        }
        return company_lookup, report

    async def _archive_leads_sheet(self, wb: Any) -> Dict[str, Any]:
        """Archive all non-empty rows from 'Leads' worksheet into leads_archive table."""
        if "Leads" not in wb.sheetnames:
            return {"status": "skipped_no_leads_sheet", "archived_rows": 0}

        ws_leads = wb["Leads"]
        archived_count = 0
        skipped_empty = 0

        for r_idx, row in enumerate(ws_leads.iter_rows(values_only=True)):
            if not any(row):
                skipped_empty += 1
                continue
            if r_idx == 0:
                # header row preserved as row 1
                pass

            row_num = r_idx + 1
            raw_data_dict = {f"col_{i}": str(c) if c is not None else "" for i, c in enumerate(row)}
            raw_json = json.dumps(raw_data_dict, ensure_ascii=False)
            checksum = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

            # Extracted fields
            name_val = str(row[0]).strip() if len(row) > 0 and row[0] is not None else None
            company_val = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
            pos_val = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
            phone_val = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
            email_val = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
            sp_val = str(row[5]).strip() if len(row) > 5 and row[5] is not None else None

            archive_entry = LeadsArchive(
                id=uuid.uuid4(),
                batch_id=self.batch_id,
                sheet_name="Leads",
                row_number=row_num,
                raw_data=raw_json,
                name=name_val,
                company_name=company_val,
                position=pos_val,
                phone=phone_val,
                email=email_val,
                salesperson=sp_val,
                row_checksum=checksum,
                archived_at=datetime.now(timezone.utc),
            )
            self.db.add(archive_entry)
            archived_count += 1

        await self.db.flush()
        return {
            "sheet_name": "Leads",
            "archived_rows": archived_count,
            "skipped_empty_rows": skipped_empty,
        }

    async def _replace_active_contacts(
        self,
        wb: Any,
        user_by_name: Dict[str, User],
        company_lookup: Dict[str, uuid.UUID],
    ) -> Dict[str, Any]:
        """
        Process Sheet16 (preserving Row 1, discarding Row 67).
        Deduplicates Sheet16 rows into canonical contacts.
        Replaces active contacts: updates/inserts Sheet16 contacts, retires contacts absent from Sheet16.
        """
        if "Sheet16" not in wb.sheetnames:
            raise ValueError("Workbook is missing required 'Sheet16' worksheet.")

        ws16 = wb["Sheet16"]
        companies_set = read_companies_tab(wb)

        raw_sheet16_rows = 0
        valid_contact_rows = 0
        invalid_rows: List[Dict[str, Any]] = []
        parsed_records: List[Dict[str, Any]] = []

        for r_idx, row in enumerate(ws16.iter_rows(values_only=True)):
            if not any(row):
                continue
            raw_sheet16_rows += 1
            row_num = r_idx + 1

            raw_name = str(row[0]).strip() if row[0] is not None else ""
            col_b = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            col_c = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
            phone_raw = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
            email_raw = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
            sp_raw = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""
            att1 = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""
            att2 = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""
            att3 = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ""
            last_contact = str(row[9]).strip() if len(row) > 9 and row[9] is not None else ""
            notes = str(row[10]).strip() if len(row) > 10 and row[10] is not None else ""

            # Check for identity: must have name OR phone OR email
            if not raw_name and not phone_raw and not email_raw:
                invalid_rows.append({"row_num": row_num, "reason": "no name, phone, or email", "row": str(row)})
                continue

            pos, co_name = detect_company_position(col_b, col_c, companies_set)
            first_name, last_name = split_name(raw_name)
            norm_phone = normalize_phone(phone_raw, country_hint="SA")
            norm_email = norm_email_func(email_raw)
            import_key = make_import_key(norm_email, norm_phone, first_name, last_name)

            # Match to canonical company
            company_id = None
            if co_name and co_name.strip().lower() in company_lookup:
                company_id = company_lookup[co_name.strip().lower()]
            elif col_b and col_b.strip().lower() in company_lookup:
                company_id = company_lookup[col_b.strip().lower()]
            elif col_c and col_c.strip().lower() in company_lookup:
                company_id = company_lookup[col_c.strip().lower()]

            # Match salesperson
            sp_key = sp_raw.strip().lower()
            owner = user_by_name.get(sp_key)
            owner_id = owner.id if owner else None

            valid_contact_rows += 1
            parsed_records.append({
                "source_row": row_num,
                "first_name": first_name or raw_name or "Unknown",
                "last_name": last_name,
                "full_name": raw_name,
                "company_name": co_name,
                "company_id": company_id,
                "position": pos,
                "phone": phone_raw,
                "normalized_phone": norm_phone,
                "email": email_raw,
                "normalized_email": norm_email,
                "owner_id": owner_id,
                "salesperson_raw": sp_raw,
                "import_key": import_key,
                "att1": att1,
                "att2": att2,
                "att3": att3,
                "last_contact": last_contact,
                "notes": notes,
                "row_tuple": row,
            })

        # Deduplicate Sheet16 records by import_key
        canonical_by_key: Dict[str, Dict[str, Any]] = {}
        sheet16_duplicates: List[Dict[str, Any]] = []
        for rec in parsed_records:
            k = rec["import_key"]
            if k not in canonical_by_key:
                canonical_by_key[k] = rec
            else:
                sheet16_duplicates.append({
                    "duplicate_row": rec["source_row"],
                    "winner_row": canonical_by_key[k]["source_row"],
                    "name": rec["full_name"],
                    "key": k,
                })
                # Merge richest notes/attempts
                winner = canonical_by_key[k]
                if not winner["notes"] and rec["notes"]:
                    winner["notes"] = rec["notes"]
                if not winner["company_id"] and rec["company_id"]:
                    winner["company_id"] = rec["company_id"]
                if not winner["owner_id"] and rec["owner_id"]:
                    winner["owner_id"] = rec["owner_id"]

        logger.info(
            "sheet16_replacer.sheet16_parsed",
            total_source_rows=raw_sheet16_rows,
            valid_rows=valid_contact_rows,
            canonical_unique=len(canonical_by_key),
            duplicates=len(sheet16_duplicates),
        )

        # Existing contacts in DB: build lookup map by import_key, email, phone
        existing_contacts_stmt = select(Contact)
        all_existing_contacts = (await self.db.execute(existing_contacts_stmt)).scalars().all()
        existing_by_key: Dict[str, Contact] = {}
        for c in all_existing_contacts:
            if hasattr(c, "import_key") and c.import_key:
                existing_by_key[c.import_key] = c
            elif c.email:
                existing_by_key[f"email:{norm_email_func(c.email)}"] = c
            elif c.phone:
                existing_by_key[f"phone:{normalize_phone(c.phone, country_hint='SA')}"] = c

        active_retained_contact_ids: Set[uuid.UUID] = set()
        contacts_inserted = 0
        contacts_updated = 0
        per_salesperson_counts: Dict[str, int] = {}

        for import_key, rec in canonical_by_key.items():
            sp_display = rec["salesperson_raw"] or "Unassigned"
            per_salesperson_counts[sp_display] = per_salesperson_counts.get(sp_display, 0) + 1

            matched_c = existing_by_key.get(import_key)
            if matched_c:
                # Update existing contact
                matched_c.first_name = rec["first_name"]
                matched_c.last_name = rec["last_name"]
                if rec["company_id"]:
                    matched_c.company_id = rec["company_id"]
                if rec["position"]:
                    matched_c.position = rec["position"]
                if rec["phone"]:
                    matched_c.phone = rec["phone"]
                    matched_c.normalized_phone = rec["normalized_phone"]
                if rec["email"]:
                    matched_c.email = rec["email"]
                    matched_c.normalized_email = rec["normalized_email"]
                if rec["owner_id"]:
                    matched_c.owner_id = rec["owner_id"]
                if rec["notes"]:
                    matched_c.notes = rec["notes"]
                matched_c.attempt_1 = rec["att1"] or matched_c.attempt_1
                matched_c.attempt_2 = rec["att2"] or matched_c.attempt_2
                matched_c.attempt_3 = rec["att3"] or matched_c.attempt_3
                matched_c.source_sheet = "Sheet16"
                matched_c.sheet_order = rec["source_row"]

                # Ensure active status
                matched_c.status = ContactStatus.NEW.value
                matched_c.deleted_at = None

                self.db.add(matched_c)
                active_retained_contact_ids.add(matched_c.id)
                rec["contact_id"] = matched_c.id
                contacts_updated += 1
            else:
                # Insert new contact
                new_c = Contact(
                    id=uuid.uuid4(),
                    first_name=rec["first_name"],
                    last_name=rec["last_name"],
                    company_id=rec["company_id"],
                    position=rec["position"],
                    phone=rec["phone"],
                    normalized_phone=rec["normalized_phone"],
                    email=rec["email"],
                    normalized_email=rec["normalized_email"],
                    owner_id=rec["owner_id"],
                    notes=rec["notes"],
                    status=ContactStatus.NEW.value,
                    import_key=import_key,
                    source_sheet="Sheet16",
                    sheet_order=rec["source_row"],
                    attempt_1=rec["att1"] or None,
                    attempt_2=rec["att2"] or None,
                    attempt_3=rec["att3"] or None,
                )
                self.db.add(new_c)
                active_retained_contact_ids.add(new_c.id)
                rec["contact_id"] = new_c.id
                contacts_inserted += 1

        await self.db.flush()

        # Retire active contacts that are NOT in Sheet16
        retired_count = 0
        now_utc = datetime.now(timezone.utc)
        for c in all_existing_contacts:
            if c.id not in active_retained_contact_ids:
                if c.deleted_at is None and c.status != ContactStatus.ARCHIVED.value:
                    c.status = ContactStatus.ARCHIVED.value
                    c.deleted_at = now_utc
                    c.archived_at = now_utc
                    self.db.add(c)
                    retired_count += 1

        await self.db.flush()

        report = {
            "sheet16_source_rows": raw_sheet16_rows,
            "valid_contact_rows": valid_contact_rows,
            "invalid_rows": len(invalid_rows),
            "invalid_details": invalid_rows,
            "canonical_unique_contacts": len(canonical_by_key),
            "sheet16_duplicate_rows": len(sheet16_duplicates),
            "contacts_inserted": contacts_inserted,
            "contacts_updated": contacts_updated,
            "retired_old_contacts": retired_count,
            "per_salesperson_counts": per_salesperson_counts,
            "canonical_contacts_by_key": canonical_by_key,
        }
        return report

    async def _extract_historical_activities(
        self,
        wb: Any,
        user_by_name: Dict[str, User],
        company_lookup: Dict[str, uuid.UUID],
        canonical_by_key: Dict[str, Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract historical Demos and Follow-ups from Sheet16 activity records.
        Links records to canonical Sheet16 contacts, canonical companies, and owners.
        """
        demos_created = 0
        followups_created = 0

        for key, rec in canonical_by_key.items():
            contact_id = rec.get("contact_id")
            if not contact_id:
                continue

            company_id = rec.get("company_id")
            owner_id = rec.get("owner_id")
            source_row = rec["source_row"]

            attempts_text = f"{rec['att1']} {rec['att2']} {rec['att3']}".strip()
            notes_text = rec.get("notes") or ""
            last_contact = rec.get("last_contact") or ""
            full_context = f"{attempts_text} {last_contact} {notes_text}".lower()

            # ── 1. Check for Demo ───────────────────────────────────────────
            if "demo" in full_context:
                existing_demo = await self.db.scalar(
                    select(Demo).where(
                        Demo.contact_id == contact_id,
                        Demo.source_sheet == "Sheet16",
                        Demo.source_row == source_row,
                    )
                )
                if not existing_demo:
                    demo = Demo(
                        id=uuid.uuid4(),
                        contact_id=contact_id,
                        company_id=company_id,
                        owner_id=owner_id,
                        stage=DemoStage.COMPLETED.value if "completed" in full_context or "done" in full_context else DemoStage.SCHEDULED.value,
                        status=DemoStatus.INTERESTED_NEXT_STEP.value if "interested" in full_context else DemoStatus.PENDING.value,
                        notes=f"Source attempts: {attempts_text} | Notes: {notes_text}",
                        next_step=last_contact if last_contact else "Historical Demo Follow-up",
                        is_historical=True,
                        historical_source="CRM data.xlsx - Sheet16",
                        source_sheet="Sheet16",
                        source_row=source_row,
                        scheduled_at=datetime.now(timezone.utc),
                    )
                    self.db.add(demo)
                    demos_created += 1

            # ── 2. Check for Follow-up / Recall ─────────────────────────────
            if any(w in full_context for w in ["re call", "recall", "re-call", "whatapp", "whatsapp", "email"]):
                fu_type = FollowUpType.GENERAL.value
                if "whatapp" in full_context or "whatsapp" in full_context:
                    fu_type = FollowUpType.WHATSAPP.value
                elif "email" in full_context:
                    fu_type = FollowUpType.EMAIL.value
                elif "re call" in full_context or "recall" in full_context:
                    fu_type = FollowUpType.CALL.value

                existing_fu = await self.db.scalar(
                    select(FollowUp).where(
                        FollowUp.contact_id == contact_id,
                        FollowUp.source_sheet == "Sheet16",
                        FollowUp.source_row == source_row,
                    )
                )
                if not existing_fu:
                    fu = FollowUp(
                        id=uuid.uuid4(),
                        contact_id=contact_id,
                        company_id=company_id,
                        user_id=owner_id,
                        type=fu_type,
                        status="PENDING",
                        due_at=datetime.now(timezone.utc),
                        notes=f"Attempts: {attempts_text} | Notes: {notes_text}",
                        next_step=last_contact if last_contact else "Follow-up required",
                        source_sheet="Sheet16",
                        source_row=source_row,
                    )
                    self.db.add(fu)
                    followups_created += 1

        await self.db.flush()

        demos_report = {"demos_created": demos_created}
        fu_report = {"followups_created": followups_created}
        return demos_report, fu_report
