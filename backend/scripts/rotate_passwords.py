"""
Issue a fresh random temporary password to every active user and print them ONCE.
Use this right after deploying: every current account still uses the default
passwords that used to be in the source code.

    cd backend
    .venv/Scripts/python -m scripts.rotate_passwords            # dry run: list accounts
    .venv/Scripts/python -m scripts.rotate_passwords --apply    # rotate + print new passwords
    .venv/Scripts/python -m scripts.rotate_passwords --apply --only saleh@alphapromena.com
"""
import argparse
import asyncio
import secrets

from sqlalchemy import select

from app.core.security import hash_password
from app.database import AsyncSessionLocal, engine
from app.models.user import User


async def run(apply: bool, only: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(User)
            .where(User.deleted_at.is_(None), User.is_active.is_(True))
            .order_by(User.email)
        )
        if only:
            stmt = stmt.where(User.email.in_(only))
        users = (await db.execute(stmt)).scalars().all()
        print(f"{'APPLY' if apply else 'DRY RUN'}: {len(users)} account(s)\n")
        for u in users:
            if apply:
                pw = secrets.token_urlsafe(12)
                u.password_hash = hash_password(pw)
                u.is_locked = False
                u.login_attempts = 0
                u.locked_until = None
                db.add(u)
                print(f"  {u.email:<32} {u.role:<10} {pw}")
            else:
                print(f"  {u.email:<32} {u.role}")
        if apply:
            await db.commit()
            print("\nSave these now - they are not stored anywhere. Users can change them in Settings.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--only", nargs="*", default=[], help="limit to these emails")
    args = parser.parse_args()
    asyncio.run(run(args.apply, args.only))
