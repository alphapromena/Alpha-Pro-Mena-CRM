import asyncio
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models.contact import Contact
from app.models.user import User

async def run_audit():
    async with AsyncSessionLocal() as session:
        # Delete old seed contacts that are not in the real spreadsheet
        # (Seed contacts have import_key starting with 'seed_' or have no source_sheet and were created with fake names)
        res_seed = await session.execute(
            text("DELETE FROM contacts WHERE import_key LIKE 'seed_%' OR (source_sheet IS NULL AND sheet_order IS NULL)")
        )
        await session.commit()
        print(f"Purged fake/seed contacts. Total affected: {res_seed.rowcount}")

        # Breakdown by source_sheet
        print("\n=== CONTACTS BY SOURCE SHEET ===")
        res = await session.execute(
            select(Contact.source_sheet, func.count(Contact.id)).where(Contact.deleted_at.is_(None)).group_by(Contact.source_sheet)
        )
        for s, count in res.all():
            print(f"Sheet '{s}': {count} contacts")

        # First lead in Leads sheet for each sales rep
        print("\n=== FIRST LEAD PER SALES REP (LEADS SHEET) ===")
        res_users = await session.execute(select(User).where(User.deleted_at.is_(None)))
        for u in res_users.scalars().all():
            res_first = await session.execute(
                select(Contact).options(selectinload(Contact.company))
                .where(Contact.owner_id == u.id, Contact.deleted_at.is_(None), Contact.source_sheet == "Leads")
                .order_by(Contact.sheet_order.asc())
                .limit(1)
            )
            first_c = res_first.scalars().first()
            if first_c:
                c_name = first_c.company.name if first_c.company else "None"
                print(f"Rep: {u.first_name} {u.last_name or ''} ({u.role})")
                print(f"  -> First Lead in Sheet: Row #{first_c.sheet_order} | {first_c.full_name} | {c_name} | {first_c.position} | {first_c.phone} | {first_c.email}")

        # Kush Goel record
        print("\n=== KUSH GOEL ===")
        res_kush = await session.execute(
            select(Contact).options(selectinload(Contact.company), selectinload(Contact.owner))
            .where(Contact.first_name == "Kush", Contact.last_name == "Goel")
        )
        kush = res_kush.scalars().first()
        if kush:
            print(f"Name: {kush.full_name}")
            print(f"Company: {kush.company.name if kush.company else None}")
            print(f"Position: {kush.position}")
            print(f"Phone: {kush.phone}")
            print(f"Normalized Phone: {kush.normalized_phone}")
            print(f"Email: {kush.email}")
            print(f"Owner: {kush.owner.first_name if kush.owner else None}")
            print(f"Sheet Order: {kush.sheet_order}")
            print(f"Attempts: 1={kush.attempt_1} | 2={kush.attempt_2} | 3={kush.attempt_3}")

if __name__ == "__main__":
    asyncio.run(run_audit())
