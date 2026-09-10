"""
Backfill for accounts that predate email verification.

The email_verified column was added with DEFAULT FALSE, which retroactively marked
every existing account unverified and redirected the whole team to /verify-email.
These tests pin exactly which rows the repair touches, and which it must not.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auto_migrate import _backfill_pre_verification_accounts
from app.core.security import hash_password, hash_token, normalize_email
from app.database import Base
from app.models.user import User, UserRole


@pytest_asyncio.fixture
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'backfill.sqlite3').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


def user(prefix, **kwargs) -> User:
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@alphapromena.com"
    defaults = dict(
        email=email,
        normalized_email=normalize_email(email),
        first_name=prefix.capitalize(),
        last_name="User",
        password_hash=hash_password("SomePassword123!"),
        role=UserRole.SALES_USER,
        is_active=True,
        must_change_password=False,
        email_verified=False,
        verification_token_hash=None,
        deleted_at=None,
    )
    defaults.update(kwargs)
    return User(**defaults)


@pytest.mark.asyncio
async def test_verifies_established_accounts_only(session):
    """
    Four shapes, one of which qualifies. The other three each fail exactly one of
    the three guard conditions.
    """
    established = user("established")
    bootstrapped = user("bootstrapped", must_change_password=True)
    mid_verification = user("midverify", verification_token_hash=hash_token("pending-token"))
    already_verified = user("alreadyok", email_verified=True)

    session.add_all([established, bootstrapped, mid_verification, already_verified])
    await session.commit()

    updated = await _backfill_pre_verification_accounts(session)
    await session.commit()

    assert updated == 1

    for u in (established, bootstrapped, mid_verification, already_verified):
        await session.refresh(u)

    assert established.email_verified is True, "an account with a personal password should be verified"
    assert bootstrapped.email_verified is False, "a shared temporary password must not self-verify"
    assert mid_verification.email_verified is False, "someone mid-verification is left alone"
    assert already_verified.email_verified is True


@pytest.mark.asyncio
async def test_skips_soft_deleted_rows(session):
    from datetime import datetime, timezone

    deleted = user("deleted", deleted_at=datetime.now(timezone.utc))
    live = user("live")
    session.add_all([deleted, live])
    await session.commit()

    updated = await _backfill_pre_verification_accounts(session)
    await session.commit()

    assert updated == 1
    await session.refresh(deleted)
    await session.refresh(live)
    assert deleted.email_verified is False
    assert live.email_verified is True


@pytest.mark.asyncio
async def test_is_idempotent(session):
    """A second run must match nothing, so repeated startups are harmless."""
    session.add_all([user("one"), user("two")])
    await session.commit()

    first = await _backfill_pre_verification_accounts(session)
    await session.commit()
    second = await _backfill_pre_verification_accounts(session)
    await session.commit()

    assert first == 2
    assert second == 0


@pytest.mark.asyncio
async def test_no_rows_is_not_an_error(session):
    assert await _backfill_pre_verification_accounts(session) == 0


@pytest.mark.asyncio
async def test_runs_as_part_of_the_sqlite_migration(session, monkeypatch):
    """The step is wired into the migration, not just callable on its own."""
    from app.core import auto_migrate

    session.add(user("wired"))
    await session.commit()

    await auto_migrate._migrate_sqlite(session)
    await session.commit()

    rows = (await session.execute(select(User).where(User.email_verified.is_(True)))).scalars().all()
    assert len(rows) == 1
