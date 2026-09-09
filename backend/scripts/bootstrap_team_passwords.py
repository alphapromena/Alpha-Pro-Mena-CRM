"""
Bootstrap script to update the seven core team user accounts with the temporary
bootstrap password, forced password change on first login, and reset lock status.

Preserves existing user IDs, roles, teams, contacts, demos, tasks, and audit logs.
Does NOT output plaintext passwords in logs or stdout.
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import structlog
from sqlalchemy import select

from app.core.security import hash_password, normalize_email
from app.database import AsyncSessionLocal, engine
from app.models.user import User, UserRole, Team

logger = structlog.get_logger(__name__)

BOOTSTRAP_USERS = [
    {"email": "saleh@alphapromena.com", "first_name": "Saleh", "role": UserRole.USER, "team_name": "Saudi Financial & Banking"},
    {"email": "hassan@alphapromena.com", "first_name": "Hassan", "role": UserRole.USER, "team_name": "MENA Enterprise Sales"},
    {"email": "amin@alphapromena.com", "first_name": "Amin", "role": UserRole.USER, "team_name": "MENA Enterprise Sales"},
    {"email": "ghaida@alphapromena.com", "first_name": "Ghaida", "role": UserRole.USER, "team_name": "Gulf Public Sector"},
    {"email": "qusai@alphapromena.com", "first_name": "Qusai", "role": UserRole.TEAM_LEAD, "team_name": "Saudi Financial & Banking"},
    {"email": "aseel@alphapromena.com", "first_name": "Aseel", "role": UserRole.DATA_OPS, "team_name": "MENA Enterprise Sales"},
    {"email": "abdallah@alphapromena.com", "first_name": "Abdallah", "role": UserRole.MANAGER, "team_name": "MENA Enterprise Sales"},
]


async def bootstrap_team_passwords(target_password: str = "123456789") -> None:
    hashed = hash_password(target_password)
    async with AsyncSessionLocal() as db:
        for u_info in BOOTSTRAP_USERS:
            norm_email = normalize_email(u_info["email"])
            stmt = select(User).where(User.normalized_email == norm_email, User.deleted_at.is_(None))
            user = (await db.execute(stmt)).scalar_one_or_none()

            if user:
                # Update existing user safely
                user.password_hash = hashed
                user.must_change_password = True
                user.is_locked = False
                user.login_attempts = 0
                user.locked_until = None
                user.is_active = True
                db.add(user)
                print(f"[UPDATED] {u_info['email']:<32} | Role: {user.role:<10} | must_change_password=True")
            else:
                # Find team if exists
                team_stmt = select(Team).where(Team.name == u_info["team_name"])
                team = (await db.execute(team_stmt)).scalar_one_or_none()
                team_id = team.id if team else None

                new_user = User(
                    email=u_info["email"],
                    normalized_email=norm_email,
                    first_name=u_info["first_name"],
                    last_name="",
                    password_hash=hashed,
                    role=u_info["role"],
                    team_id=team_id,
                    is_active=True,
                    is_locked=False,
                    login_attempts=0,
                    must_change_password=True,
                    email_verified=False,
                )
                db.add(new_user)
                print(f"[CREATED] {u_info['email']:<32} | Role: {u_info['role']:<10} | must_change_password=True")

        await db.commit()
    await engine.dispose()
    print("\nBootstrap complete: All 7 team members have temporary password set with must_change_password=True.")


if __name__ == "__main__":
    asyncio.run(bootstrap_team_passwords())
