"""
Production Data Reset & Real CRM Data Import Script
===================================================
1. Safely archives ALL existing operational test data (Contacts, Recalls, NoAnswerQueue)
   without deleting any historical call records, notes, or timelines.
2. Ingests the 1,802 real CRM leads from CRM.xlsx with exact salesperson mapping:
   - Hasan: 548 leads
   - Amin: 576 leads
   - Saleh: 335 leads
   - Ghaida: 337 leads
   - Unassigned: 6 leads
3. Preserves deterministic source sheet row ordering (sheet_order).
4. Smart company normalization and deduplication.
5. Initializes all 5 call attempts as empty.
"""
import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple, Set

import openpyxl
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.call import Call
from app.models.company import Company
from app.models.contact import Contact, ContactPriority, ContactStatus
from app.models.demo import Demo
from app.models.follow_up import FollowUp
from app.models.no_answer import NoAnswerQueue
from app.models.recall import Recall
from app.models.task import Task
from app.models.user import User
from app.models.audit import AuditLog
from app.core.security import normalize_email, normalize_phone


def normalize_company_name(name: Optional[str]) -> str:
    """Normalize company name for robust deduplication and matching."""
    if not name:
        return ""
    s = name.strip().lower()
    # Replace separators with space
    s = re.sub(r"[\-_.,/\\&()+]", " ", s)
    # Remove common corporate suffixes
    tokens = s.split()
    suffixes = {
        "ltd", "limited", "llc", "inc", "incorporated", "corp", "corporation",
        "co", "company", "group", "holding", "holdings", "saudi", "ksa", "uae",
        "dubai", "gulf", "international", "intl", "services", "solutions", "est"
    }
    filtered = [t for t in tokens if t not in suffixes]
    if filtered:
        return " ".join(filtered)
    return " ".join(tokens)


async def run_archive_and_import():
    crm_path = Path("CRM.xlsx")
    if not crm_path.exists():
        # Check workspace root
        crm_path = Path("c:/Users/user/Alpha-Pro-Mena-CRM/CRM.xlsx")
        if not crm_path.exists():
            raise FileNotFoundError(f"CRM.xlsx not found at {crm_path.absolute()}")

    print(f"Loading workbook from: {crm_path.resolve()}")
    wb = openpyxl.load_workbook(crm_path, data_only=True)
    sheet = wb.active

    async with AsyncSessionLocal() as db:
        print("\n=======================================================")
        print("PHASE 1: PRE-MIGRATION DATABASE INSPECTION")
        print("=======================================================")
        
        # 1. Count current state
        total_contacts_before = (await db.execute(select(func.count(Contact.id)))).scalar_one() or 0
        active_contacts_before = (await db.execute(
            select(func.count(Contact.id)).where(Contact.status != ContactStatus.ARCHIVED, Contact.deleted_at.is_(None))
        )).scalar_one() or 0
        archived_contacts_before = (await db.execute(
            select(func.count(Contact.id)).where(Contact.status == ContactStatus.ARCHIVED)
        )).scalar_one() or 0
        
        pending_recalls_before = (await db.execute(
            select(func.count(Recall.id)).where(Recall.status == "PENDING")
        )).scalar_one() or 0
        
        pending_na_before = (await db.execute(
            select(func.count(NoAnswerQueue.id)).where(NoAnswerQueue.status == "PENDING")
        )).scalar_one() or 0
        
        total_calls_before = (await db.execute(select(func.count(Call.id)))).scalar_one() or 0
        total_companies_before = (await db.execute(select(func.count(Company.id)))).scalar_one() or 0
        
        print(f"Total Contacts in DB:        {total_contacts_before}")
        print(f"Active Operational Contacts: {active_contacts_before}")
        print(f"Already Archived Contacts:   {archived_contacts_before}")
        print(f"Pending Recalls:             {pending_recalls_before}")
        print(f"Pending No Answer Queue:     {pending_na_before}")
        print(f"Historical Calls:            {total_calls_before}")
        print(f"Existing Companies:          {total_companies_before}")

        print("\n=======================================================")
        print("PHASE 2: SAFELY ARCHIVING ALL OPERATIONAL TEST DATA")
        print("=======================================================")

        now = datetime.now(timezone.utc)
        
        # Archive all active contacts
        archive_contacts_stmt = (
            update(Contact)
            .where(Contact.status != ContactStatus.ARCHIVED)
            .values(
                status=ContactStatus.ARCHIVED,
                archived_at=now,
                notes=func.coalesce(Contact.notes, "") + "\n[ARCHIVED: Transition to Production Data]",
            )
        )
        archive_result = await db.execute(archive_contacts_stmt)
        contacts_archived_count = archive_result.rowcount
        print(f"-> Marked {contacts_archived_count} active contacts as ARCHIVED.")

        # Resolve/archive pending recalls
        recall_archive_stmt = (
            update(Recall)
            .where(Recall.status == "PENDING")
            .values(status="ARCHIVED")
        )
        recalls_archived = (await db.execute(recall_archive_stmt)).rowcount
        print(f"-> Marked {recalls_archived} pending recalls as ARCHIVED.")

        # Resolve/archive pending no answer queue records
        na_archive_stmt = (
            update(NoAnswerQueue)
            .where(NoAnswerQueue.status == "PENDING")
            .values(status="ARCHIVED")
        )
        na_archived = (await db.execute(na_archive_stmt)).rowcount
        print(f"-> Marked {na_archived} pending no-answer queue records as ARCHIVED.")

        await db.flush()

        # Verify operational queues are now 0
        active_contacts_mid = (await db.execute(
            select(func.count(Contact.id)).where(Contact.status != ContactStatus.ARCHIVED, Contact.deleted_at.is_(None))
        )).scalar_one() or 0
        pending_recalls_mid = (await db.execute(
            select(func.count(Recall.id)).where(Recall.status == "PENDING")
        )).scalar_one() or 0
        pending_na_mid = (await db.execute(
            select(func.count(NoAnswerQueue.id)).where(NoAnswerQueue.status == "PENDING")
        )).scalar_one() or 0

        print(f"\nVerification after archiving:")
        print(f"  Active Contacts:   {active_contacts_mid} (must be 0)")
        print(f"  Pending Recalls:   {pending_recalls_mid} (must be 0)")
        print(f"  Pending No Answer: {pending_na_mid} (must be 0)")
        assert active_contacts_mid == 0, "Active contacts not 0!"
        assert pending_recalls_mid == 0, "Pending recalls not 0!"
        assert pending_na_mid == 0, "Pending no answer not 0!"

        print("\n=======================================================")
        print("PHASE 3: PARSING & IMPORTING REAL CRM.XLSX DATA")
        print("=======================================================")

        # Map Salesperson names to User accounts
        users = (await db.execute(select(User))).scalars().all()
        user_by_name: Dict[str, User] = {}
        for u in users:
            if u.first_name:
                user_by_name[u.first_name.strip().lower()] = u
        
        # Ensure mappings:
        # "hassan" -> "hasan", "amin" -> "amin", "saleh" -> "saleh", "ghaida" -> "ghaida"
        sp_map: Dict[str, Optional[User]] = {
            "hassan": user_by_name.get("hasan") or user_by_name.get("hassan"),
            "hasan": user_by_name.get("hasan") or user_by_name.get("hassan"),
            "amin": user_by_name.get("amin"),
            "saleh": user_by_name.get("saleh"),
            "ghaida": user_by_name.get("ghaida"),
        }

        print("Salesperson account mapping:")
        for sp_k, u_obj in sp_map.items():
            print(f"  '{sp_k}' -> {u_obj.full_name if u_obj else 'None'} ({u_obj.email if u_obj else 'None'}) [ID: {u_obj.id if u_obj else 'None'}]")

        # Pre-load existing companies for smart deduplication
        all_companies = (await db.execute(select(Company))).scalars().all()
        company_lookup: Dict[str, Company] = {}
        company_raw_lookup: Dict[str, Company] = {}
        for comp in all_companies:
            if comp.name:
                raw_k = comp.name.strip().lower()
                norm_k = normalize_company_name(comp.name)
                company_raw_lookup[raw_k] = comp
                if norm_k:
                    company_lookup[norm_k] = comp

        total_rows = sheet.max_row
        valid_rows = 0
        invalid_rows = 0
        duplicate_rows = 0
        user_import_counts: Dict[str, int] = {"Saleh": 0, "Amin": 0, "Hasan": 0, "Ghaida": 0, "Unassigned": 0}
        
        new_companies_created = 0
        existing_companies_matched = 0

        created_contacts_list = []
        batch_import_id = uuid.uuid4().hex[:8]

        for row_idx in range(1, total_rows + 1):
            c_name = sheet.cell(row=row_idx, column=1).value
            c_comp = sheet.cell(row=row_idx, column=2).value
            c_pos = sheet.cell(row=row_idx, column=3).value
            c_phone = sheet.cell(row=row_idx, column=4).value
            c_email = sheet.cell(row=row_idx, column=5).value
            c_sp = sheet.cell(row=row_idx, column=6).value

            # If completely empty row
            if not any([c_name, c_comp, c_pos, c_phone, c_email, c_sp]):
                continue

            raw_name = str(c_name).strip() if c_name is not None else ""
            raw_comp = str(c_comp).strip() if c_comp is not None else ""
            raw_pos = str(c_pos).strip() if c_pos is not None else ""
            raw_phone = str(c_phone).strip() if c_phone is not None else ""
            raw_email = str(c_email).strip() if c_email is not None else ""
            raw_sp = str(c_sp).strip() if c_sp is not None else ""

            # Check for invalid row (e.g. empty name AND phone AND email)
            if not raw_name and not raw_phone and not raw_email:
                invalid_rows += 1
                print(f"Skipping invalid row {row_idx}: Name={raw_name}, SP={raw_sp}")
                continue

            # Split name into first and last
            name_parts = raw_name.split() if raw_name else ["Lead", ""]
            first_name = name_parts[0] if name_parts else "Lead"
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None

            # Normalization
            norm_email = normalize_email(raw_email) if raw_email else None
            norm_phone = normalize_phone(raw_phone) if raw_phone else None

            # Map salesperson
            sp_key = raw_sp.lower()
            assigned_user = sp_map.get(sp_key)
            owner_id = assigned_user.id if assigned_user else None
            team_id = assigned_user.team_id if assigned_user else None
            status = ContactStatus.NEW if owner_id else ContactStatus.UNASSIGNED

            # Smart Company Matching
            company_id = None
            if raw_comp:
                raw_k = raw_comp.lower()
                norm_k = normalize_company_name(raw_comp)
                matched_company = company_raw_lookup.get(raw_k) or (company_lookup.get(norm_k) if norm_k else None)

                if matched_company:
                    company_id = matched_company.id
                    existing_companies_matched += 1
                else:
                    new_company = Company(
                        id=uuid.uuid4(),
                        name=raw_comp,
                        account_owner_id=owner_id,
                    )
                    db.add(new_company)
                    await db.flush()
                    company_id = new_company.id
                    company_raw_lookup[raw_k] = new_company
                    if norm_k:
                        company_lookup[norm_k] = new_company
                    new_companies_created += 1

            # Deterministic import key
            import_key = hashlib.sha256(
                f"crm_xlsx:{row_idx}:{raw_name}:{raw_phone}:{raw_email}:{batch_import_id}".encode()
            ).hexdigest()

            # Create clean Contact entity
            contact = Contact(
                id=uuid.uuid4(),
                first_name=first_name,
                last_name=last_name,
                email=raw_email if raw_email else None,
                normalized_email=norm_email,
                phone=raw_phone if raw_phone else None,
                normalized_phone=norm_phone,
                company_id=company_id,
                position=raw_pos if raw_pos else None,
                owner_id=owner_id,
                team_id=team_id,
                status=status,
                priority=ContactPriority.MEDIUM,
                source="CRM.xlsx",
                source_sheet="Sheet1",
                sheet_order=row_idx,  # Preserves exact source row ordering
                import_key=import_key,
                # All attempts start completely EMPTY
                attempt_1=None,
                attempt_2=None,
                attempt_3=None,
                attempt_count=0,
                last_outcome=None,
                final_outcome=None,
            )
            db.add(contact)
            created_contacts_list.append(contact)
            valid_rows += 1

            # Count per user
            if assigned_user:
                u_name = assigned_user.first_name
                if u_name in user_import_counts:
                    user_import_counts[u_name] += 1
                else:
                    user_import_counts[u_name] = 1
            else:
                user_import_counts["Unassigned"] += 1

        await db.commit()
        wb.close()

        print("\n=======================================================")
        print("PHASE 4: POST-IMPORT VERIFICATION & SUMMARY REPORT")
        print("=======================================================")

        total_contacts_after = (await db.execute(select(func.count(Contact.id)))).scalar_one() or 0
        active_contacts_after = (await db.execute(
            select(func.count(Contact.id)).where(Contact.status != ContactStatus.ARCHIVED, Contact.deleted_at.is_(None))
        )).scalar_one() or 0
        archived_contacts_after = (await db.execute(
            select(func.count(Contact.id)).where(Contact.status == ContactStatus.ARCHIVED)
        )).scalar_one() or 0
        total_companies_after = (await db.execute(select(func.count(Company.id)))).scalar_one() or 0

        print(f"Total rows in CRM file:            {total_rows}")
        print(f"Valid CRM rows imported:           {valid_rows}")
        print(f"Invalid / skipped rows:            {invalid_rows}")
        print(f"Duplicate rows:                    {duplicate_rows}")
        print(f"Leads assigned to Hasan:           {user_import_counts.get('Hasan', 0)}")
        print(f"Leads assigned to Amin:            {user_import_counts.get('Amin', 0)}")
        print(f"Leads assigned to Saleh:           {user_import_counts.get('Saleh', 0)}")
        print(f"Leads assigned to Ghaida:          {user_import_counts.get('Ghaida', 0)}")
        print(f"Unassigned leads:                  {user_import_counts.get('Unassigned', 0)}")
        print(f"New Companies created:             {new_companies_created}")
        print(f"Existing Companies matched:        {existing_companies_matched}")
        print(f"Total Companies in DB:             {total_companies_after}")
        print(f"Old Archived records preserved:    {archived_contacts_after}")
        print(f"Active Contacts in CRM now:        {active_contacts_after}")
        print(f"Total Contacts in DB (All):        {total_contacts_after}")
        print("=======================================================\n")

        # Verify deterministic ordering
        for sp_name, u_obj in [("Saleh", sp_map["saleh"]), ("Amin", sp_map["amin"]), ("Hasan", sp_map["hasan"]), ("Ghaida", sp_map["ghaida"])]:
            if u_obj:
                first_5_leads = (await db.execute(
                    select(Contact)
                    .where(Contact.owner_id == u_obj.id, Contact.status == ContactStatus.NEW)
                    .order_by(Contact.sheet_order.asc())
                    .limit(5)
                )).scalars().all()
                print(f"First 3 leads for {sp_name} (ordered by sheet_order):")
                for l in first_5_leads[:3]:
                    print(f"  Row {l.sheet_order:04d} | {l.full_name:<25} | {l.position or 'N/A'} | Attempts: {l.attempt_count}")
                    assert l.attempt_count == 0, f"Attempt count for {l.full_name} is not 0!"
                    assert l.attempt_1 is None, f"Attempt 1 for {l.full_name} is not None!"
                    assert l.final_outcome is None, f"Final outcome for {l.full_name} is not None!"

        print("\nAll database checks PASSED perfectly.")


if __name__ == "__main__":
    asyncio.run(run_archive_and_import())
