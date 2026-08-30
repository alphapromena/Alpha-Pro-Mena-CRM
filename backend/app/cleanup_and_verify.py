import asyncio
from sqlalchemy import text, select, func
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models.contact import Contact
from app.models.user import User

async def clean_and_verify():
    async with AsyncSessionLocal() as session:
        # Delete dummy contacts from Demo sheet header rows
        await session.execute(
            text("""
                DELETE FROM contacts 
                WHERE (phone IS NULL OR phone = '') 
                  AND (email IS NULL OR email = '') 
                  AND (first_name IN ('JUN', 'JUL', 'AUG', 'MARIA', 'Ghaida', 'July', 'June', 'NAME', 'Saleh', 'None', 'None None')
                       OR first_name IS NULL)
            """)
        )
        await session.commit()

        # Check total contacts
        res_total = await session.execute(select(func.count(Contact.id)).where(Contact.deleted_at.is_(None)))
        print(f"Total Clean Contacts in DB: {res_total.scalar_one()}")

        # Check First Lead for each rep in Leads sheet order
        print("\n=== VERIFYING FIRST LEAD PER SALES REP (SHEET ORDER) ===")
        res_users = await session.execute(select(User).where(User.deleted_at.is_(None)))
        for u in res_users.scalars().all():
            res_first = await session.execute(
                select(Contact).options(selectinload(Contact.company))
                .where(Contact.owner_id == u.id, Contact.deleted_at.is_(None), Contact.sheet_order.is_not(None))
                .order_by(Contact.sheet_order.asc())
                .limit(1)
            )
            first_c = res_first.scalars().first()
            if first_c:
                c_name = first_c.company.name if first_c.company else "None"
                print(f"Rep: {u.first_name} {u.last_name or ''} ({u.role})")
                print(f"  -> First Lead in Sheet: Row #{first_c.sheet_order} | {first_c.full_name} | {c_name} | {first_c.position} | {first_c.phone} | {first_c.email}")

        # Check Kush Goel
        print("\n=== KUSH GOEL VERIFICATION ===")
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
    asyncio.run(clean_and_verify())
