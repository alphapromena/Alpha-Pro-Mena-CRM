import asyncio
import uuid
from sqlalchemy import select, update
from app.database import get_db_context
from app.models.contact import Contact, ContactStatus

async def test():
    async with get_db_context() as db:
        # Find one unassigned contact (not archived)
        stmt = select(Contact).where(
            Contact.owner_id.is_(None),
            Contact.deleted_at.is_(None),
            Contact.status != ContactStatus.ARCHIVED
        ).limit(1)
        res = await db.execute(stmt)
        c = res.scalar_one_or_none()
        print("Found contact:", c.id if c else None, "name:", c.first_name if c else None, "status:", c.status if c else None)
        if c:
            # Let's test updating it using ORM
            # Get Saleh's user id
            from app.models.user import User
            u_stmt = select(User).where(User.first_name == "Saleh").limit(1)
            u_res = await db.execute(u_stmt)
            saleh = u_res.scalar_one()
            print("Saleh id:", saleh.id)
            
            c.owner_id = saleh.id
            c.status = ContactStatus.PENDING_CLAIM
            db.add(c)
            await db.flush()
            print("Flush successful!")

if __name__ == "__main__":
    asyncio.run(test())
