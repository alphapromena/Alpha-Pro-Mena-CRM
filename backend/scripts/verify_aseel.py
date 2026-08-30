import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User

async def check():
    async with AsyncSessionLocal() as session:
        u = (await session.execute(select(User).where(User.email == "aseel@alphapromena.com"))).scalar_one_or_none()
        if u:
            print(f"Aseel exists: {u.first_name} | {u.email} | Role: {u.role} | ID: {u.id} | Active: {u.is_active}")
        else:
            print("Aseel NOT found in DB")

asyncio.run(check())
