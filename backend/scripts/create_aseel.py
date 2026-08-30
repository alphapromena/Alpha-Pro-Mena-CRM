"""Create Aseel's MANAGER account (data/lead operations role)."""
import asyncio
import secrets
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password, normalize_email
from sqlalchemy import select


async def create_aseel():
    temp_password = secrets.token_urlsafe(12)
    async with AsyncSessionLocal() as session:
        # Check if Aseel already exists
        existing = (await session.execute(
            select(User).where(User.normalized_email == normalize_email("aseel@alphapromena.com"))
        )).scalar_one_or_none()

        if existing:
            print(f"Updating existing Aseel: {existing.first_name} ({existing.role})")
            existing.password_hash = hash_password(temp_password)
            existing.role = UserRole.DATA_OPS
            existing.is_locked = False
            existing.login_attempts = 0
            existing.first_name = "Aseel"
            existing.last_name = ""
            session.add(existing)
            await session.commit()
            print(f"Aseel credentials reset. Temporary password (shown once): {temp_password}")
            return

        aseel = User(
            email="aseel@alphapromena.com",
            normalized_email=normalize_email("aseel@alphapromena.com"),
            first_name="Aseel",
            last_name="",  # Last name left blank
            password_hash=hash_password(temp_password),
            role=UserRole.DATA_OPS,
            is_active=True,
            is_locked=False,
            login_attempts=0,
            lead_capacity=500,
            theme_preference="black_beige",
            preferred_language="en",
        )
        session.add(aseel)
        await session.commit()
        await session.refresh(aseel)

        print(f"Created Aseel: {aseel.first_name} | {aseel.email} | Role: {aseel.role}")
        print(f"  Temporary password (shown once): {temp_password}")
        print("  Role: DATA_OPS (Data Operations & Google Sheets Ingestion only)")


if __name__ == "__main__":
    asyncio.run(create_aseel())
