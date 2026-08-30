import asyncio
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.contact import Contact

async def normalize_ownership():
    async with AsyncSessionLocal() as db:
        # Load primary users
        res = await db.execute(select(User).where(User.deleted_at.is_(None)))
        users = res.scalars().all()
        user_by_name = {u.first_name.lower(): u for u in users if "@alphapromena.com" in u.email}
        
        print("Primary users:", list(user_by_name.keys()))
        
        # Point all contacts to primary @alphapromena.com users
        for u in users:
            if "@alphapro.com" in u.email and u.first_name.lower() in user_by_name:
                primary = user_by_name[u.first_name.lower()]
                if primary.id != u.id:
                    await db.execute(
                        update(Contact).where(Contact.owner_id == u.id).values(owner_id=primary.id)
                    )
        
        # Assign some unassigned / Oman / BFSI leads to Qusai
        qusai_user = user_by_name.get("qusai")
        if qusai_user:
            # Assign first 100 unassigned leads to Qusai
            unassigned_res = await db.execute(
                select(Contact).where(Contact.owner_id.is_(None)).limit(80)
            )
            for c in unassigned_res.scalars().all():
                c.owner_id = qusai_user.id
                db.add(c)
                
        await db.commit()
        print("Ownership normalized successfully!")

if __name__ == "__main__":
    asyncio.run(normalize_ownership())
