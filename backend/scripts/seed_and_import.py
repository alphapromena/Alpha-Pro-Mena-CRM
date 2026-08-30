import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import structlog
from sqlalchemy import select, text, func

from app.database import AsyncSessionLocal, engine, Base
from app.core.security import hash_password, normalize_email, normalize_phone
from app.models.user import User, UserRole, Team
from app.models.company import Company
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.call import Call
from app.models.demo import Demo, DemoStage
from app.models.recall import Recall, RecallStatus
from app.models.follow_up import FollowUp, FollowUpType
from app.models.no_answer import NoAnswerQueue

logger = structlog.get_logger(__name__)

async def seed_and_import():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe migration for new columns on SQLite
        for col in ["attempt_1", "attempt_2", "attempt_3"]:
            try:
                await conn.execute(text(f"ALTER TABLE contacts ADD COLUMN {col} VARCHAR(100)"))
            except Exception:
                pass  # column already exists

    async with AsyncSessionLocal() as db:
        print("1. Creating / Updating System Teams & 6 Official Users (Phase 4)...")
        
        # Teams
        teams_data = [
            ("MENA Enterprise Sales", "High-tier enterprise accounts across UAE, Saudi, Qatar"),
            ("Saudi Financial & Banking", "Specialized Saudi BFSI accounts & fintechs"),
            ("Gulf Public Sector", "Governmental & semi-gov organizations"),
        ]
        team_map = {}
        for name, desc in teams_data:
            res = await db.execute(select(Team).where(Team.name == name))
            team = res.scalar_one_or_none()
            if not team:
                team = Team(name=name, description=desc)
                db.add(team)
                await db.flush()
            team_map[name] = team

        # Official System Users — first names only for internal employees
        users_to_seed = [
            {
                "email": "saleh@alphapromena.com",
                "aliases": ["saleh@alphapro.com"],
                "first_name": "Saleh",
                "last_name": "",
                "password": "<set-password>",
                "role": UserRole.USER,
                "team": "Saudi Financial & Banking",
            },
            {
                "email": "hasan@alphapromena.com",
                "aliases": ["hasan@alphapro.com", "hassan@alphapromena.com", "hassan@alphapro.com"],
                "first_name": "Hasan",
                "last_name": "",
                "password": "<set-password>",
                "role": UserRole.USER,
                "team": "MENA Enterprise Sales",
            },
            {
                "email": "amin@alphapromena.com",
                "aliases": ["amin@alphapro.com"],
                "first_name": "Amin",
                "last_name": "",
                "password": "<set-password>",
                "role": UserRole.USER,
                "team": "MENA Enterprise Sales",
            },
            {
                "email": "ghaida@alphapromena.com",
                "aliases": ["ghaida@alphapro.com"],
                "first_name": "Ghaida",
                "last_name": "",
                "password": "<set-password>",
                "role": UserRole.USER,
                "team": "Gulf Public Sector",
            },
            {
                "email": "qusai@alphapromena.com",
                "aliases": ["qusai@alphapro.com"],
                "first_name": "Qusai",
                "last_name": "",
                "password": "<set-password>",
                "role": UserRole.TEAM_LEAD,
                "team": "MENA Enterprise Sales",
            },
            {
                "email": "aseel@alphapromena.com",
                "aliases": ["aseel@alphapro.com"],
                "first_name": "Aseel",
                "last_name": "",
                "password": "<set-password>",
                "role": UserRole.TEAM_LEAD,
                "team": "MENA Enterprise Sales",
            },
            {
                "email": "abdallah@alphapromena.com",
                "aliases": ["abdallah@alphapro.com", "abdullah@alphapromena.com", "manager@alphapromena.com", "manager@alphapro.com"],
                "first_name": "Abdullah",
                "last_name": "",
                "password": "<set-password>",
                "role": UserRole.MANAGER,
                "team": "MENA Enterprise Sales",
            },
        ]

        user_objects = {}
        for u_data in users_to_seed:
            email_primary = u_data["email"]
            norm_primary = normalize_email(email_primary)
            team_obj = team_map.get(u_data["team"])
            
            all_emails = [email_primary] + u_data.get("aliases", [])
            norm_emails = [normalize_email(e) for e in all_emails]
            
            res = await db.execute(select(User).where(User.normalized_email.in_(norm_emails)))
            existing_users = res.scalars().all()
            existing_user = existing_users[0] if existing_users else None
            
            pwd_hash = hash_password(u_data["password"])
            
            if existing_user:
                existing_user.email = email_primary
                existing_user.normalized_email = norm_primary
                existing_user.first_name = u_data["first_name"]
                existing_user.last_name = u_data["last_name"]
                existing_user.password_hash = pwd_hash
                existing_user.role = u_data["role"]
                existing_user.team_id = team_obj.id if team_obj else None
                existing_user.is_active = True
                existing_user.is_locked = False
                existing_user.login_attempts = 0
                db.add(existing_user)
                user_objects[u_data["first_name"].lower()] = existing_user
                print(f"  [OK] Updated user: {email_primary} ({u_data['role']})")
                
                # If there are redundant duplicate alias accounts, reassign their FKs to existing_user and remove duplicates
                for dup_user in existing_users[1:]:
                    if dup_user.id != existing_user.id:
                        await db.execute(text("UPDATE contacts SET owner_id = :main_id WHERE owner_id = :dup_id"), {"main_id": existing_user.id.hex, "dup_id": dup_user.id.hex})
                        await db.execute(text("UPDATE calls SET user_id = :main_id WHERE user_id = :dup_id"), {"main_id": existing_user.id.hex, "dup_id": dup_user.id.hex})
                        await db.delete(dup_user)
            else:
                new_user = User(
                    email=email_primary,
                    normalized_email=norm_primary,
                    first_name=u_data["first_name"],
                    last_name=u_data["last_name"],
                    password_hash=pwd_hash,
                    role=u_data["role"],
                    team_id=team_obj.id if team_obj else None,
                    is_active=True,
                    is_locked=False,
                    login_attempts=0,
                    lead_capacity=500 if u_data["role"] == UserRole.USER else 1000,
                )
                db.add(new_user)
                await db.flush()
                user_objects[u_data["first_name"].lower()] = new_user
                print(f"  [OK] Created user: {email_primary} ({u_data['role']})")

        await db.commit()

        # Migrate any remaining contacts/activities from legacy hassan to hasan
        hasan_user = user_objects.get("hasan")
        if hasan_user:
            res_old_hassan = await db.execute(select(User).where(User.normalized_email == "hassan@alphapromena.com"))
            old_hassan = res_old_hassan.scalar_one_or_none()
            if old_hassan and old_hassan.id != hasan_user.id:
                await db.execute(text("UPDATE contacts SET owner_id = :new_id WHERE owner_id = :old_id"), {"new_id": hasan_user.id.hex, "old_id": old_hassan.id.hex})
                await db.execute(text("UPDATE calls SET user_id = :new_id WHERE user_id = :old_id"), {"new_id": hasan_user.id.hex, "old_id": old_hassan.id.hex})
                await db.commit()

        print("Users and teams setup completed successfully.")

    # 2. Import Leads, Attempts, Recalls, Demos, and Follow-ups
    print("\n2. Importing real data from Gulf Leads .xlsx...")
    import openpyxl
    xlsx_file = Path("c:/Users/user/Alpha-Pro-Mena-CRM/Gulf Leads .xlsx")
    if not xlsx_file.exists():
        print(f"ERROR: {xlsx_file} not found!")
        return

    wb = openpyxl.load_workbook(xlsx_file, data_only=True)
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.deleted_at.is_(None)))
        all_users = res.scalars().all()
        user_id_by_name = {}
        for u in all_users:
            user_id_by_name[u.first_name.lower().strip()] = u.id
            if u.first_name.lower() == "hasan":
                user_id_by_name["hassan"] = u.id
            if u.email:
                user_id_by_name[u.email.split("@")[0].lower().strip()] = u.id

        company_cache = {}
        res_comp = await db.execute(select(Company))
        for c in res_comp.scalars().all():
            company_cache[c.name.strip().lower()] = c.id

        async def get_or_create_comp(comp_name: str):
            if not comp_name or not str(comp_name).strip():
                return None
            clean_name = str(comp_name).strip()
            key = clean_name.lower()
            if key in company_cache:
                return company_cache[key]
            new_c = Company(name=clean_name)
            db.add(new_c)
            await db.flush()
            company_cache[key] = new_c.id
            return new_c.id

        # 2A. Process Leads Master Sheet
        ws_leads = wb["Leads"]
        print("Processing 'Leads' sheet with 1st, 2nd, 3rd attempts...")

        # Load existing contacts map by phone/email
        existing_contacts_by_key = {}
        res_contacts = await db.execute(select(Contact))
        for c in res_contacts.scalars().all():
            if c.normalized_email:
                existing_contacts_by_key[f"email:{c.normalized_email}"] = c
            if c.normalized_phone:
                existing_contacts_by_key[f"phone:{c.normalized_phone}"] = c

        leads_count = 0
        calls_created = 0
        recalls_created = 0
        no_answer_created = 0
        followups_created = 0

        for row in ws_leads.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            
            full_name = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
            company_name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            position = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
            phone = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
            email = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
            salesperson = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""
            att1 = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""
            att2 = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""
            att3 = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ""
            last_contact = str(row[9]).strip() if len(row) > 9 and row[9] is not None else ""
            notes = str(row[10]).strip() if len(row) > 10 and row[10] is not None else ""

            if not full_name and not phone and not email:
                continue

            parts = full_name.rsplit(" ", 1) if full_name else ("", "")
            first_name = parts[0] if len(parts) > 0 else "Unknown"
            last_name = parts[1] if len(parts) > 1 else ""

            clean_email = normalize_email(email) if email else ""
            clean_phone = normalize_phone(phone) if phone else ""
            
            owner_id = None
            if salesperson:
                sp_key = salesperson.lower().strip()
                if sp_key == "hassan":
                    sp_key = "hasan"
                owner_id = user_id_by_name.get(sp_key)
            if not owner_id and company_name:
                comp_lower = company_name.lower()
                if "oman" in comp_lower or "muscat" in comp_lower:
                    owner_id = user_id_by_name.get("amin")

            # Determine latest outcome and status
            attempts = [a for a in [att1, att2, att3] if a and a.lower() not in ["none", ""]]
            last_outcome = attempts[-1] if attempts else None
            
            status = ContactStatus.NEW
            attempts_text = f"{att1} {att2} {att3}".lower()
            if "demo" in attempts_text:
                status = ContactStatus.DEMO_SCHEDULED
            elif "asked for email" in attempts_text:
                status = ContactStatus.EMAIL_REQUESTED
            elif "asked for whatapp" in attempts_text or "whatsapp" in attempts_text:
                status = ContactStatus.WHATSAPP_REQUESTED
            elif "re call" in attempts_text:
                status = ContactStatus.RECALL_SCHEDULED
            elif "not interested" in attempts_text:
                status = ContactStatus.NOT_INTERESTED
            elif "no answer" in attempts_text or len(attempts) >= 2:
                status = ContactStatus.NO_ANSWER
            elif len(attempts) == 1:
                status = ContactStatus.CONTACTED

            # Check if contact already exists
            contact = None
            if clean_email and f"email:{clean_email}" in existing_contacts_by_key:
                contact = existing_contacts_by_key[f"email:{clean_email}"]
            elif clean_phone and f"phone:{clean_phone}" in existing_contacts_by_key:
                contact = existing_contacts_by_key[f"phone:{clean_phone}"]

            if not contact:
                comp_id = await get_or_create_comp(company_name)
                contact = Contact(
                    first_name=first_name or "Unknown",
                    last_name=last_name or None,
                    company_id=comp_id,
                    position=position or None,
                    email=email or None,
                    normalized_email=clean_email or None,
                    phone=phone or None,
                    normalized_phone=clean_phone or None,
                    notes=notes or None,
                    owner_id=owner_id,
                    status=status,
                    attempt_count=len(attempts),
                    last_outcome=last_outcome,
                    attempt_1=att1 or None,
                    attempt_2=att2 or None,
                    attempt_3=att3 or None,
                    source="Excel Import (Leads)",
                )
                db.add(contact)
                await db.flush()
                if clean_email:
                    existing_contacts_by_key[f"email:{clean_email}"] = contact
                if clean_phone:
                    existing_contacts_by_key[f"phone:{clean_phone}"] = contact
                leads_count += 1
            else:
                # Update existing contact attempt fields & status
                contact.attempt_1 = att1 or contact.attempt_1
                contact.attempt_2 = att2 or contact.attempt_2
                contact.attempt_3 = att3 or contact.attempt_3
                contact.attempt_count = max(contact.attempt_count or 0, len(attempts))
                if last_outcome:
                    contact.last_outcome = last_outcome
                if owner_id and not contact.owner_id:
                    contact.owner_id = owner_id
                db.add(contact)

            # Create historical Call records for attempts if not present
            for i, att in enumerate(attempts, start=1):
                if att and att.lower() not in ["none", ""]:
                    call = Call(
                        contact_id=contact.id,
                        user_id=owner_id or user_id_by_name.get("saleh"),
                        outcome=att.strip(),
                        duration_seconds=120 if "demo" in att.lower() else 45,
                        called_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc) + timedelta(days=i * 3),
                        attempt_number=i,
                        notes=f"Attempt {i}: {att}" + (f" | {notes}" if notes else ""),
                    )
                    db.add(call)
                    calls_created += 1

            # Create Recall record if Re Call
            if "re call" in attempts_text:
                recall = Recall(
                    contact_id=contact.id,
                    user_id=owner_id or user_id_by_name.get("saleh"),
                    scheduled_at=datetime(2026, 7, 10, 11, 0, tzinfo=timezone.utc),
                    status=RecallStatus.PENDING,
                    notes=f"Recall requested from attempt history: {notes}",
                )
                db.add(recall)
                recalls_created += 1

            # Create NoAnswerQueue entry if latest attempt is No Answer
            if last_outcome and "no answer" in last_outcome.lower():
                no_ans = NoAnswerQueue(
                    contact_id=contact.id,
                    user_id=owner_id,
                    attempt_number=len(attempts),
                    last_attempt_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
                    status="PENDING",
                )
                db.add(no_ans)
                no_answer_created += 1

            # Create FollowUp entry if email or whatsapp requested
            if "asked for email" in attempts_text or "asked for whatapp" in attempts_text:
                fu_type = FollowUpType.EMAIL if "email" in attempts_text else FollowUpType.WHATSAPP
                fu = FollowUp(
                    contact_id=contact.id,
                    user_id=owner_id or user_id_by_name.get("saleh"),
                    type=fu_type,
                    status="PENDING",
                    due_at=datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc),
                    notes=f"Prospect requested materials via {fu_type}: {notes}",
                )
                db.add(fu)
                followups_created += 1

        await db.commit()
        print(f"  [OK] Leads processed. New contacts: {leads_count}, Calls: {calls_created}, Recalls: {recalls_created}, NoAnswer: {no_answer_created}, FollowUps: {followups_created}")

        # 2B. Process Demo Sheet
        if "Demo" in wb.sheetnames:
            ws_demo = wb["Demo"]
            print("Processing 'Demo' sheet...")
            demos_created = 0
            current_rep = "saleh"
            
            for row in ws_demo.iter_rows(min_row=1, values_only=True):
                if not any(row):
                    continue
                
                # Check for salesperson header row
                col0 = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
                if col0.lower() in ["saleh", "hasan", "hassan", "amin", "ghaida", "qusai", "abdallah"]:
                    current_rep = "hasan" if col0.lower() in ["hasan", "hassan"] else col0.lower()
                    continue

                contact_name = col0
                company_name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
                position = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
                phone = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
                email = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
                rep_name = str(row[5]).strip() if len(row) > 5 and row[5] is not None else current_rep
                date_str = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""
                notes_str = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""

                if not contact_name and not company_name and not phone:
                    continue

                rep_clean = rep_name.lower().strip()
                if rep_clean in ["hassan", "hasan"]:
                    rep_clean = "hasan"
                rep_user_id = user_id_by_name.get(rep_clean) or user_id_by_name.get("saleh")

                clean_email = normalize_email(email) if email else ""
                clean_phone = normalize_phone(phone) if phone else ""

                contact = None
                if clean_email and f"email:{clean_email}" in existing_contacts_by_key:
                    contact = existing_contacts_by_key[f"email:{clean_email}"]
                elif clean_phone and f"phone:{clean_phone}" in existing_contacts_by_key:
                    contact = existing_contacts_by_key[f"phone:{clean_phone}"]

                if not contact:
                    comp_id = await get_or_create_comp(company_name)
                    parts = contact_name.rsplit(" ", 1) if contact_name else ("", "")
                    contact = Contact(
                        first_name=parts[0] or "Demo Prospect",
                        last_name=parts[1] if len(parts) > 1 else None,
                        company_id=comp_id,
                        position=position or None,
                        email=email or None,
                        normalized_email=clean_email or None,
                        phone=phone or None,
                        normalized_phone=clean_phone or None,
                        owner_id=rep_user_id,
                        status=ContactStatus.DEMO_SCHEDULED,
                        source="Excel Import (Demo Sheet)",
                    )
                    db.add(contact)
                    await db.flush()
                    if clean_email:
                        existing_contacts_by_key[f"email:{clean_email}"] = contact
                    if clean_phone:
                        existing_contacts_by_key[f"phone:{clean_phone}"] = contact

                # Determine Stage & Scheduled Date
                stage = DemoStage.SCHEDULED
                notes_combined = f"{date_str} | {notes_str}".strip(" |")
                notes_lower = notes_combined.lower()
                
                if "done" in notes_lower or "completed" in notes_lower:
                    stage = DemoStage.COMPLETED
                elif "cancel" in notes_lower or "ملغي" in notes_lower:
                    stage = DemoStage.CANCELLED
                elif "reschedul" in notes_lower or "تأجيل" in notes_lower or "بعد العيد" in notes_lower or "اجل" in notes_lower:
                    stage = DemoStage.RESCHEDULED
                elif "no show" in notes_lower or "لم يحضر" in notes_lower:
                    stage = DemoStage.NO_SHOW

                demo = Demo(
                    contact_id=contact.id,
                    company_id=contact.company_id,
                    owner_id=rep_user_id,
                    stage=stage,
                    scheduled_at=datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc),
                    notes=notes_combined or "Product demonstration scheduled from Excel import.",
                )
                db.add(demo)
                demos_created += 1

            await db.commit()
            print(f"  [OK] Demos processed. Created: {demos_created} demo records.")

        # 2C. Process Ghaida & Amin Follow-up Sheets
        for fu_sheet, rep_key in [("Ghaida fu", "ghaida"), ("Amin fu", "amin")]:
            if fu_sheet in wb.sheetnames:
                ws_fu = wb[fu_sheet]
                rep_user_id = user_id_by_name.get(rep_key)
                fu_added = 0
                for row in ws_fu.iter_rows(min_row=1, values_only=True):
                    if not any(row):
                        continue
                    c_name = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
                    comp_name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
                    pos = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
                    ph = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
                    em = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
                    note_val = str(row[6]).strip() if len(row) > 6 and row[6] is not None else ""

                    if not c_name and not ph and not em:
                        continue

                    clean_em = normalize_email(em) if em else ""
                    clean_ph = normalize_phone(ph) if ph else ""

                    contact = None
                    if clean_em and f"email:{clean_em}" in existing_contacts_by_key:
                        contact = existing_contacts_by_key[f"email:{clean_em}"]
                    elif clean_ph and f"phone:{clean_ph}" in existing_contacts_by_key:
                        contact = existing_contacts_by_key[f"phone:{clean_ph}"]

                    if not contact:
                        comp_id = await get_or_create_comp(comp_name)
                        parts = c_name.rsplit(" ", 1) if c_name else ("", "")
                        contact = Contact(
                            first_name=parts[0] or "Prospect",
                            last_name=parts[1] if len(parts) > 1 else None,
                            company_id=comp_id,
                            position=pos or None,
                            email=em or None,
                            normalized_email=clean_em or None,
                            phone=ph or None,
                            normalized_phone=clean_ph or None,
                            owner_id=rep_user_id,
                            status=ContactStatus.EMAIL_REQUESTED if "email" in note_val.lower() else ContactStatus.IN_PROGRESS,
                            source=f"Excel Import ({fu_sheet})",
                        )
                        db.add(contact)
                        await db.flush()
                        if clean_em:
                            existing_contacts_by_key[f"email:{clean_em}"] = contact
                        if clean_ph:
                            existing_contacts_by_key[f"phone:{clean_ph}"] = contact

                    follow_up = FollowUp(
                        contact_id=contact.id,
                        user_id=rep_user_id,
                        type=FollowUpType.EMAIL if "email" in note_val.lower() else FollowUpType.GENERAL,
                        status="PENDING",
                        due_at=datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc),
                        notes=f"Dedicated follow-up ({fu_sheet}): {note_val}",
                    )
                    db.add(follow_up)
                    fu_added += 1

                await db.commit()
                print(f"  [OK] Processed {fu_sheet}: Added {fu_added} follow-ups.")

    print("\nPhase 4 Seed & Import completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_and_import())
