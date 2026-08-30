"""Update database users: remove surnames for internal system employees and configure Aseel as TEAM_LEAD."""
import asyncio
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole


async def clean_users():
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            old_name = f"{u.first_name} {u.last_name}"
            # Standardize internal user first names
            if u.email.startswith("saleh"):
                u.first_name = "Saleh"
                u.last_name = ""
            elif u.email.startswith("amin"):
                u.first_name = "Amin"
                u.last_name = ""
            elif u.email.startswith("abdallah") or u.email.startswith("abdullah"):
                u.first_name = "Abdullah"
                u.last_name = ""
                u.role = UserRole.MANAGER  # Confirm Abdullah is MANAGER
            elif u.email.startswith("qusai"):
                u.first_name = "Qusai"
                u.last_name = ""
                u.role = UserRole.TEAM_LEAD
            elif u.email.startswith("aseel"):
                u.first_name = "Aseel"
                u.last_name = ""
                u.role = UserRole.TEAM_LEAD  # Set Aseel to TEAM_LEAD
            elif u.email.startswith("ghaida"):
                u.first_name = "Ghaida"
                u.last_name = ""
            elif u.email.startswith("hasan"):
                u.first_name = "Hasan"
                u.last_name = ""
            else:
                # Any other internal user: clean last name
                u.last_name = ""

            session.add(u)
            print(f"Updated User: {old_name} -> {u.first_name} (Role: {u.role}, Email: {u.email})")

        await session.commit()
        print("\nAll database users successfully cleaned & updated!")


if __name__ == "__main__":
    asyncio.run(clean_users())
