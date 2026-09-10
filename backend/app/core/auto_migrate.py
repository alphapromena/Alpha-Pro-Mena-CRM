"""
Automated database migration and team account bootstrap runner.
Ensures all required columns, tables, and team credentials exist
on startup without requiring external CLI commands in serverless environments.
"""
import asyncio
import traceback
from typing import Optional, List, Dict, Any
import structlog
from sqlalchemy import text, select, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password, normalize_email
from app.models.user import User, UserRole, Team

settings = get_settings()
logger = structlog.get_logger(__name__)

# The Alembic revision whose schema the DDL in this module reproduces.
# Keep in sync with backend/alembic/versions/ when new revisions are added.
AUTO_MIGRATE_REVISION = "c5a1f8e23901"

# Revisions strictly OLDER than AUTO_MIGRATE_REVISION. A database stamped with
# one of these really has been brought up to AUTO_MIGRATE_REVISION by the DDL
# below, so advancing its stamp is correct. Any other value -- in particular a
# revision newer than AUTO_MIGRATE_REVISION -- is left untouched so a database
# that has moved ahead is never stamped backwards.
SUPERSEDED_REVISIONS = ("b6d7df55ae73",)


def _get_bootstrap_password() -> str:
    """
    Return the bootstrap password from the BOOTSTRAP_PASSWORD environment variable.
    In production, missing this variable is a hard startup error — team members
    cannot log in without a known bootstrap credential.
    In non-production environments, falls back to a local-dev-only default and
    logs a warning so developers are not blocked.
    """
    pw = getattr(settings, "bootstrap_password", "") or ""
    if pw:
        return pw
    if settings.app_env == "production":
        raise RuntimeError(
            "BOOTSTRAP_PASSWORD env var is not set. "
            "Set it on Vercel before deploying. "
            "All bootstrap team accounts require a known temporary password."
        )
    logger.warning(
        "auto_migrate.bootstrap_password_missing",
        hint="Set BOOTSTRAP_PASSWORD env var. Using local-dev fallback.",
    )
    return "ChangeMe_LocalDev_Only!"

_migration_lock = asyncio.Lock()
_migration_completed = False

BOOTSTRAP_MEMBERS = [
    {"email": "saleh@alphapromena.com",    "first_name": "Saleh",    "role": UserRole.USER,      "team_name": "Saudi Financial & Banking"},
    {"email": "hassan@alphapromena.com",   "first_name": "Hassan",   "role": UserRole.USER,      "team_name": "MENA Enterprise Sales"},
    {"email": "amin@alphapromena.com",     "first_name": "Amin",     "role": UserRole.USER,      "team_name": "MENA Enterprise Sales"},
    {"email": "ghaida@alphapromena.com",   "first_name": "Ghaida",   "role": UserRole.USER,      "team_name": "Gulf Public Sector"},
    {"email": "qusai@alphapromena.com",    "first_name": "Qusai",    "role": UserRole.TEAM_LEAD, "team_name": "Saudi Financial & Banking"},
    {"email": "aseel@alphapromena.com",    "first_name": "Aseel",    "role": UserRole.DATA_OPS,  "team_name": "MENA Enterprise Sales"},
    {"email": "abdallah@alphapromena.com", "first_name": "Abdallah", "role": UserRole.MANAGER,   "team_name": "MENA Enterprise Sales"},
]


async def auto_migrate_if_needed(session: AsyncSession) -> None:
    """
    Idempotently apply schema updates and bootstrap team accounts.
    Runs once per process lifecycle. Thread/coroutine safe.
    """
    global _migration_completed
    if _migration_completed or settings.app_env == "test":
        return

    async with _migration_lock:
        if _migration_completed:
            return

        results = await _run_migrations(session)
        if results["success"]:
            _migration_completed = True
            logger.info("auto_migrate.completed", steps=results["steps"])
        else:
            logger.error(
                "auto_migrate.failed",
                error=results.get("error"),
                traceback=results.get("traceback"),
            )


async def run_migrations_now(session: AsyncSession) -> Dict[str, Any]:
    """
    Force-run all migrations and return a detailed report.
    Called from the admin /run-migrations endpoint.
    Resets the migration flag so it runs even if already completed.
    """
    global _migration_completed
    _migration_completed = False
    result = await _run_migrations(session)
    if result["success"]:
        _migration_completed = True
    return result


async def _run_migrations(session: AsyncSession) -> Dict[str, Any]:
    """Core migration logic. Returns a result dict with success/error info."""
    steps: List[str] = []
    try:
        # Detect dialect from URL — session.bind is always None in SQLAlchemy 2.x async
        db_url = str(settings.database_url)
        dialect = "sqlite" if db_url.startswith("sqlite") else "postgresql"
        steps.append(f"dialect={dialect}")
        logger.info("auto_migrate.starting", dialect=dialect)

        if dialect == "postgresql":
            await _migrate_postgresql(session)
            steps.append("postgresql_ddl_ok")
        else:
            await _migrate_sqlite(session)
            steps.append("sqlite_ddl_ok")

        await _bootstrap_team_users(session)
        steps.append("bootstrap_ok")

        await session.commit()
        steps.append("committed")
        return {"success": True, "steps": steps}

    except Exception as exc:
        tb = traceback.format_exc()
        try:
            await session.rollback()
        except Exception:
            pass
        return {
            "success": False,
            "steps": steps,
            "error": str(exc),
            "exception_type": type(exc).__name__,
            "traceback": tb,
        }


# ─── PostgreSQL DDL ────────────────────────────────────────────────────────────

async def _migrate_postgresql(session: AsyncSession) -> None:
    """Apply all required PostgreSQL schema changes idempotently."""

    # ── 1. users table ──────────────────────────────────────────────────────
    await session.execute(text("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
            ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password   BOOLEAN   NOT NULL DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified          BOOLEAN   NOT NULL DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_hash VARCHAR(255);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_expires_at TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_sent_at    TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(255);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_sent_at   TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS theme_preference   VARCHAR(50)  NOT NULL DEFAULT 'black_beige';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10)  NOT NULL DEFAULT 'en';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at      TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS lead_capacity      INTEGER      NOT NULL DEFAULT 500;
            CREATE INDEX IF NOT EXISTS ix_users_verification_token_hash    ON users (verification_token_hash);
            CREATE INDEX IF NOT EXISTS ix_users_password_reset_token_hash  ON users (password_reset_token_hash);
            CREATE INDEX IF NOT EXISTS ix_users_must_change_password        ON users (must_change_password);
        END IF;
    END $$;
    """))

    # ── 2. demos table ──────────────────────────────────────────────────────
    await session.execute(text("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'demos') THEN
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS status           VARCHAR(50)  NOT NULL DEFAULT 'PENDING';
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS presenter        VARCHAR(255);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS attendees        TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS topics_covered   TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS summary          TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS reason           TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS next_step        TEXT;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS next_step_due_date TIMESTAMPTZ;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS report_status    VARCHAR(30)  NOT NULL DEFAULT 'NEEDS_REPORT';
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS is_historical    BOOLEAN      NOT NULL DEFAULT FALSE;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS historical_source VARCHAR(255);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS historical_date  TIMESTAMPTZ;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS created_by_id    UUID REFERENCES users(id) ON DELETE SET NULL;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS updated_by_id    UUID REFERENCES users(id) ON DELETE SET NULL;
            CREATE INDEX IF NOT EXISTS ix_demos_status          ON demos (status);
            CREATE INDEX IF NOT EXISTS ix_demos_report_status   ON demos (report_status);
            CREATE INDEX IF NOT EXISTS ix_demos_is_historical   ON demos (is_historical);
            CREATE INDEX IF NOT EXISTS ix_demos_created_by_id   ON demos (created_by_id);
            CREATE INDEX IF NOT EXISTS idx_demos_owner_status   ON demos (owner_id, status);
        END IF;
    END $$;
    """))

    # ── 3. alembic_version stamp ────────────────────────────────────────────
    await _stamp_alembic_version(session)


async def _stamp_alembic_version(session: AsyncSession) -> None:
    """
    Record that the schema above has been applied, without ever moving the
    Alembic stamp backwards.

    Two cases are safe to write:

    * the version table is empty, a fresh database adopting this schema;
    * the table holds a revision this module supersedes, meaning the DDL above
      has genuinely brought that database up to AUTO_MIGRATE_REVISION.

    Any other stamp is left alone. This previously reset the stamp to
    AUTO_MIGRATE_REVISION unconditionally, so a database already upgraded past
    that revision was rolled back on every process start and Alembic then tried
    to replay migrations that had already run.
    """
    await session.execute(text(
        "CREATE TABLE IF NOT EXISTS alembic_version ("
        "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
    ))

    # Fresh database: adopt the revision this module reproduces.
    await session.execute(
        text(
            "INSERT INTO alembic_version (version_num) "
            "SELECT :target "
            "WHERE NOT EXISTS (SELECT 1 FROM alembic_version)"
        ),
        {"target": AUTO_MIGRATE_REVISION},
    )

    # Known-older stamp: advance it. Newer or unrecognised stamps stay as they are.
    if SUPERSEDED_REVISIONS:
        stmt = text(
            "UPDATE alembic_version SET version_num = :target "
            "WHERE version_num IN :superseded"
        ).bindparams(bindparam("superseded", expanding=True))
        await session.execute(
            stmt,
            {
                "target": AUTO_MIGRATE_REVISION,
                "superseded": list(SUPERSEDED_REVISIONS),
            },
        )


# ─── SQLite DDL (local dev only) ───────────────────────────────────────────────

async def _migrate_sqlite(session: AsyncSession) -> None:
    """Apply all required SQLite schema changes idempotently."""
    res = await session.execute(text("PRAGMA table_info(users)"))
    cols = {row[1] for row in res.fetchall()}

    additions = {
        "must_change_password":          "BOOLEAN NOT NULL DEFAULT 0",
        "email_verified":                 "BOOLEAN NOT NULL DEFAULT 0",
        "verification_token_hash":        "VARCHAR(255)",
        "verification_token_expires_at":  "DATETIME",
        "verification_sent_at":           "DATETIME",
        "password_reset_token_hash":      "VARCHAR(255)",
        "password_reset_expires_at":      "DATETIME",
        "password_reset_sent_at":         "DATETIME",
        "theme_preference":               "VARCHAR(50) NOT NULL DEFAULT 'black_beige'",
        "preferred_language":             "VARCHAR(10) NOT NULL DEFAULT 'en'",
        "last_login_at":                  "DATETIME",
        "lead_capacity":                  "INTEGER NOT NULL DEFAULT 500",
    }
    for col, definition in additions.items():
        if col not in cols:
            await session.execute(
                text(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            )


# ─── Bootstrap team accounts ───────────────────────────────────────────────────

async def _bootstrap_team_users(session: AsyncSession) -> None:
    """
    Ensure all core team members exist.
    - New users: created with bootstrap password (must_change_password=True).
    - Existing users who still have must_change_password=True: password refreshed.
    - Existing users who already set a personal password: NEVER overwritten.
      Only unlocks/reactivates if locked or inactive.
    """
    bootstrap_hash = hash_password(_get_bootstrap_password())

    for member in BOOTSTRAP_MEMBERS:
        norm = normalize_email(member["email"])
        stmt = select(User).where(User.normalized_email == norm, User.deleted_at.is_(None))
        user = (await session.execute(stmt)).scalar_one_or_none()

        if user:
            if user.must_change_password:
                # Still on bootstrap password — refresh it and ensure account is usable
                user.password_hash = bootstrap_hash
                user.is_locked = False
                user.login_attempts = 0
                user.locked_until = None
                user.is_active = True
                session.add(user)
                logger.info("auto_migrate.bootstrap_reset", email=member["email"])
            else:
                # User has already set a personal password — only fix lock/active state
                changed = False
                if not user.is_active:
                    user.is_active = True
                    changed = True
                if user.is_locked:
                    user.is_locked = False
                    user.locked_until = None
                    user.login_attempts = 0
                    changed = True
                if changed:
                    session.add(user)
                    logger.info("auto_migrate.bootstrap_unlock", email=member["email"])
        else:
            # User doesn't exist yet — provision with bootstrap password
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
            logger.info("auto_migrate.bootstrap_created", email=member["email"])
