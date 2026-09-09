"""
Automated database migration and team account bootstrap runner.
Ensures that all required columns, tables, and team credentials exist
on startup without requiring external CLI commands in serverless environments.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
import structlog
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password, normalize_email
from app.models.user import User, UserRole, Team

settings = get_settings()
logger = structlog.get_logger(__name__)

_migration_lock = asyncio.Lock()
_migration_completed = False

BOOTSTRAP_MEMBERS = [
    {"email": "saleh@alphapromena.com", "first_name": "Saleh", "role": UserRole.USER, "team_name": "Saudi Financial & Banking"},
    {"email": "hassan@alphapromena.com", "first_name": "Hassan", "role": UserRole.USER, "team_name": "MENA Enterprise Sales"},
    {"email": "amin@alphapromena.com", "first_name": "Amin", "role": UserRole.USER, "team_name": "MENA Enterprise Sales"},
    {"email": "ghaida@alphapromena.com", "first_name": "Ghaida", "role": UserRole.USER, "team_name": "Gulf Public Sector"},
    {"email": "qusai@alphapromena.com", "first_name": "Qusai", "role": UserRole.TEAM_LEAD, "team_name": "Saudi Financial & Banking"},
    {"email": "aseel@alphapromena.com", "first_name": "Aseel", "role": UserRole.DATA_OPS, "team_name": "MENA Enterprise Sales"},
    {"email": "abdallah@alphapromena.com", "first_name": "Abdallah", "role": UserRole.MANAGER, "team_name": "MENA Enterprise Sales"},
]


async def auto_migrate_if_needed(session: AsyncSession) -> None:
    """
    Idempotently checks and applies schema updates and team account bootstrapping.
    Runs once per process lifecycle; thread/coroutine safe.
    """
    global _migration_completed
    if _migration_completed or settings.app_env == "test":
        return

    async with _migration_lock:
        if _migration_completed:
            return

        try:
            bind = session.bind or session.get_bind()
            dialect_name = bind.dialect.name if bind else "postgresql"

            if dialect_name == "postgresql":
                await _migrate_postgresql(session)
            elif dialect_name == "sqlite":
                await _migrate_sqlite(session)

            await _bootstrap_team_users(session)
            await session.commit()
            _migration_completed = True
            logger.info("auto_migrate.completed", dialect=dialect_name)
        except Exception as exc:
            await session.rollback()
            logger.exception("auto_migrate.failed", error=str(exc))
            # Do not set _migration_completed so subsequent requests can retry


async def _migrate_postgresql(session: AsyncSession) -> None:
    """Ensure PostgreSQL schema has all columns from 20260909 migration."""
    # 1. Users table additions
    user_ddl = """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
            ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_hash VARCHAR(255);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_expires_at TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_sent_at TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(255);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_sent_at TIMESTAMPTZ;

            CREATE INDEX IF NOT EXISTS ix_users_verification_token_hash ON users (verification_token_hash);
            CREATE INDEX IF NOT EXISTS ix_users_password_reset_token_hash ON users (password_reset_token_hash);
            CREATE INDEX IF NOT EXISTS ix_users_must_change_password ON users (must_change_password);
        END IF;
    END $$;
    """
    await session.execute(text(user_ddl))

    # 2. Demos table additions
    demo_ddl = """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'demos') THEN
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'PENDING';
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS presenter VARCHAR(255);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS attendees TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS topics_covered TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS summary TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS reason TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS next_step TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS next_step_due_date TIMESTAMPTZ;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS report_status VARCHAR(30) NOT NULL DEFAULT 'NEEDS_REPORT';
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS is_historical BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS historical_source VARCHAR(255);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS historical_date TIMESTAMPTZ;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS created_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL;

            CREATE INDEX IF NOT EXISTS ix_demos_status ON demos (status);
            CREATE INDEX IF NOT EXISTS ix_demos_next_step_due_date ON demos (next_step_due_date);
            CREATE INDEX IF NOT EXISTS ix_demos_report_status ON demos (report_status);
            CREATE INDEX IF NOT EXISTS ix_demos_is_historical ON demos (is_historical);
            CREATE INDEX IF NOT EXISTS ix_demos_historical_date ON demos (historical_date);
            CREATE INDEX IF NOT EXISTS ix_demos_created_by_id ON demos (created_by_id);
            CREATE INDEX IF NOT EXISTS idx_demos_owner_status ON demos (owner_id, status);
        END IF;
    END $$;
    """
    await session.execute(text(demo_ddl))

    # 3. Update alembic_version table
    alembic_ddl = """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version') THEN
            UPDATE alembic_version SET version_num = 'c5a1f8e23901';
        ELSE
            CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
            INSERT INTO alembic_version (version_num) VALUES ('c5a1f8e23901')
            ON CONFLICT (version_num) DO NOTHING;
        END IF;
    END $$;
    """
    await session.execute(text(alembic_ddl))


async def _migrate_sqlite(session: AsyncSession) -> None:
    """Ensure SQLite schema has all columns from 20260909 migration."""
    res = await session.execute(text("PRAGMA table_info(users)"))
    cols = {row[1] for row in res.fetchall()}
    if "must_change_password" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0"))
    if "email_verified" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0"))
    if "verification_token_hash" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN verification_token_hash VARCHAR(255)"))
    if "verification_token_expires_at" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN verification_token_expires_at DATETIME"))
    if "verification_sent_at" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN verification_sent_at DATETIME"))
    if "password_reset_token_hash" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN password_reset_token_hash VARCHAR(255)"))
    if "password_reset_expires_at" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN password_reset_expires_at DATETIME"))
    if "password_reset_sent_at" not in cols:
        await session.execute(text("ALTER TABLE users ADD COLUMN password_reset_sent_at DATETIME"))


async def _bootstrap_team_users(session: AsyncSession) -> None:
    """Ensure all seven core team members exist with temporary bootstrap password and must_change_password=True."""
    bootstrap_hash = hash_password("123456789")

    for member in BOOTSTRAP_MEMBERS:
        norm = normalize_email(member["email"])
        stmt = select(User).where(User.normalized_email == norm, User.deleted_at.is_(None))
        user = (await session.execute(stmt)).scalar_one_or_none()

        if user:
            # If user has not changed password yet or needs bootstrap
            # Safely set bootstrap credentials while preserving role, id, teams, contacts
            user.password_hash = bootstrap_hash
            user.must_change_password = True
            user.is_locked = False
            user.login_attempts = 0
            user.locked_until = None
            user.is_active = True
            session.add(user)
        else:
            # Provision user if not yet present
            team_stmt = select(Team).where(Team.name == member["team_name"])
            team = (await session.execute(team_stmt)).scalar_one_or_none()

            new_user = User(
                email=member["email"],
                normalized_email=norm,
                first_name=member["first_name"],
                last_name="",
                password_hash=bootstrap_hash,
                role=member["role"],
                team_id=team.id if team else None,
                is_active=True,
                is_locked=False,
                login_attempts=0,
                must_change_password=True,
                email_verified=False,
            )
            session.add(new_user)
