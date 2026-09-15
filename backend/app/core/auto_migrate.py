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
AUTO_MIGRATE_REVISION = "a9f3e2d1c4b7"

# Revisions strictly OLDER than AUTO_MIGRATE_REVISION. A database stamped with
# one of these really has been brought up to AUTO_MIGRATE_REVISION by the DDL
# below, so advancing its stamp is correct. Any other value -- in particular a
# revision newer than AUTO_MIGRATE_REVISION -- is left untouched so a database
# that has moved ahead is never stamped backwards.
SUPERSEDED_REVISIONS = (
    "b6d7df55ae73",
    "c5a1f8e23901",
    "a4d2c8b19e77",
    "c7e91f4a2b38",
)


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
    """
    Apply the schema, then seed the team accounts, in two separate transactions.

    These used to share one transaction and one commit at the end, so any failure in
    the bootstrap step rolled the schema changes back with it. That is what turned a
    missing BOOTSTRAP_PASSWORD into a schema outage. The two concerns are now
    independent: the schema commits on its own and stays committed regardless of what
    the bootstrap does afterwards.

    A bootstrap failure is reported so the caller retries on a later invocation, but
    it can no longer destroy work that already succeeded.
    """
    steps: List[str] = []

    # ── Phase 1: schema. Commits on its own. ─────────────────────────────────
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

        await session.commit()
        steps.append("schema_committed")
    except Exception as exc:
        tb = traceback.format_exc()
        try:
            await session.rollback()
        except Exception:
            pass
        logger.error(
            "auto_migrate.schema_failed",
            error=str(exc),
            exception_type=type(exc).__name__,
        )
        return {
            "success": False,
            "phase": "schema",
            "schema_ok": False,
            "bootstrap_ok": False,
            "steps": steps,
            "error": str(exc),
            "exception_type": type(exc).__name__,
            "traceback": tb,
        }

    # ── Phase 2: bootstrap. Isolated, so a failure here keeps the schema. ────
    try:
        await _bootstrap_team_users(session)
        await session.commit()
        steps.append("bootstrap_committed")
    except Exception as exc:
        tb = traceback.format_exc()
        try:
            await session.rollback()
        except Exception:
            pass
        logger.error(
            "auto_migrate.bootstrap_failed",
            error=str(exc),
            exception_type=type(exc).__name__,
            note="Schema changes from phase 1 remain committed.",
        )
        return {
            "success": False,
            "phase": "bootstrap",
            "schema_ok": True,
            "bootstrap_ok": False,
            "steps": steps,
            "error": str(exc),
            "exception_type": type(exc).__name__,
            "traceback": tb,
        }

    return {
        "success": True,
        "phase": "complete",
        "schema_ok": True,
        "bootstrap_ok": True,
        "steps": steps,
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

    # ── 1b. backfill accounts that predate email verification ───────────────
    # Guarded because the DDL above is itself conditional on the table existing.
    users_present = (await session.execute(
        text("SELECT to_regclass('public.users')")
    )).scalar()
    if users_present is not None:
        await _backfill_pre_verification_accounts(session)

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
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS source_sheet      VARCHAR(50);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS source_row        INTEGER;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS created_by_id    UUID REFERENCES users(id) ON DELETE SET NULL;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS updated_by_id    UUID REFERENCES users(id) ON DELETE SET NULL;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS company_name_snapshot VARCHAR(500);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS meeting_with VARCHAR(255);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS converted_to_follow_up_at TIMESTAMPTZ;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS converted_to_follow_up_id UUID;
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS import_key VARCHAR(64);
            ALTER TABLE demos ADD COLUMN IF NOT EXISTS source_file_checksum VARCHAR(64);
            CREATE INDEX IF NOT EXISTS ix_demos_status          ON demos (status);
            CREATE INDEX IF NOT EXISTS ix_demos_report_status   ON demos (report_status);
            CREATE INDEX IF NOT EXISTS ix_demos_is_historical   ON demos (is_historical);
            CREATE INDEX IF NOT EXISTS ix_demos_created_by_id   ON demos (created_by_id);
            CREATE INDEX IF NOT EXISTS idx_demos_owner_status   ON demos (owner_id, status);
            CREATE INDEX IF NOT EXISTS idx_demos_source_file    ON demos (source_file_checksum);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_demos_import_key ON demos (import_key) WHERE import_key IS NOT NULL;
        END IF;

        -- 3. follow_ups table
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'follow_ups') THEN
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS company_id   UUID REFERENCES companies(id) ON DELETE SET NULL;
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS next_step    TEXT;
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS source_sheet VARCHAR(50);
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS source_row   INTEGER;
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS company_name_snapshot VARCHAR(500);
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS meeting_with VARCHAR(255);
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS demo_id UUID REFERENCES demos(id) ON DELETE SET NULL;
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS import_key VARCHAR(64);
            ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS source_file_checksum VARCHAR(64);
            ALTER TABLE follow_ups ALTER COLUMN contact_id DROP NOT NULL;
            ALTER TABLE follow_ups ALTER COLUMN due_at DROP NOT NULL;
            CREATE INDEX IF NOT EXISTS ix_follow_ups_company_id ON follow_ups (company_id);
            CREATE INDEX IF NOT EXISTS idx_follow_ups_demo_id   ON follow_ups (demo_id);
            CREATE INDEX IF NOT EXISTS idx_follow_ups_source_file ON follow_ups (source_file_checksum);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_follow_ups_import_key ON follow_ups (import_key) WHERE import_key IS NOT NULL;
        END IF;

        -- 4. tasks table (archive support - req 12)
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tasks') THEN
            ALTER TABLE tasks ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
            ALTER TABLE tasks ADD COLUMN IF NOT EXISTS archived_by UUID REFERENCES users(id) ON DELETE SET NULL;
            CREATE INDEX IF NOT EXISTS idx_tasks_archived_at ON tasks (archived_at);
        END IF;

        -- 5. opportunities table (enrichment & company snapshot)
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'opportunities') THEN
            ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS company_name_snapshot VARCHAR(500);
            ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS contact_person VARCHAR(255);
            ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS notes TEXT;
            ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS next_step TEXT;
        END IF;

        -- 6. leads_archive table
        CREATE TABLE IF NOT EXISTS leads_archive (
            id UUID PRIMARY KEY,
            batch_id VARCHAR(100) NOT NULL,
            sheet_name VARCHAR(100) NOT NULL DEFAULT 'Leads',
            row_number INTEGER NOT NULL,
            raw_data TEXT NOT NULL,
            name VARCHAR(255),
            company_name VARCHAR(255),
            position VARCHAR(255),
            phone VARCHAR(100),
            email VARCHAR(255),
            salesperson VARCHAR(100),
            row_checksum VARCHAR(64),
            archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_leads_archive_batch ON leads_archive (batch_id);
        CREATE INDEX IF NOT EXISTS idx_leads_archive_phone ON leads_archive (phone);
        CREATE INDEX IF NOT EXISTS idx_leads_archive_email ON leads_archive (email);
        CREATE INDEX IF NOT EXISTS idx_leads_archive_salesperson ON leads_archive (salesperson);
    END $$;
    """))

    # Add foreign key constraint for converted_to_follow_up_id after both tables are verified
    await session.execute(text("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'demos' AND column_name = 'converted_to_follow_up_id') THEN
            IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'fk_demos_converted_to_follow_up') THEN
                ALTER TABLE demos ADD CONSTRAINT fk_demos_converted_to_follow_up
                FOREIGN KEY (converted_to_follow_up_id) REFERENCES follow_ups(id) ON DELETE SET NULL;
            END IF;
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            NULL; -- Safely ignore if constraint already exists or cannot be created
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


async def _backfill_pre_verification_accounts(session: AsyncSession) -> int:
    """
    Mark accounts that predate email verification as verified. Returns rows updated.

    The email_verified column was added with DEFAULT FALSE, which retroactively made
    every existing account unverified and sent the whole team to /verify-email.

    Only accounts that already set a personal password are touched. Those people
    proved control of the account before verification existed, and there is no way for
    them to verify now without help. The three conditions are the safety:

      must_change_password = FALSE   still-bootstrapped accounts are excluded, so a
                                     shared temporary password never self-verifies
      verification_token_hash IS NULL  someone mid-verification is left alone
      deleted_at IS NULL             soft-deleted rows stay untouched

    Idempotent: the email_verified = FALSE predicate means a second run matches
    nothing.
    """
    result = await session.execute(text(
        "UPDATE users SET email_verified = TRUE "
        "WHERE email_verified = FALSE "
        "AND must_change_password = FALSE "
        "AND verification_token_hash IS NULL "
        "AND deleted_at IS NULL"
    ))
    updated = result.rowcount or 0
    if updated:
        logger.info("auto_migrate.verification_backfilled", rows_updated=updated)
    else:
        logger.info("auto_migrate.verification_backfill_noop")
    return updated


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

    # Demos columns
    res_demos = await session.execute(text("PRAGMA table_info(demos)"))
    demo_cols = {row[1] for row in res_demos.fetchall()}
    if "source_sheet" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN source_sheet VARCHAR(50)"))
    if "source_row" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN source_row INTEGER"))
    if "company_name_snapshot" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN company_name_snapshot VARCHAR(500)"))
    if "meeting_with" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN meeting_with VARCHAR(255)"))
    if "converted_to_follow_up_at" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN converted_to_follow_up_at DATETIME"))
    if "converted_to_follow_up_id" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN converted_to_follow_up_id CHAR(32)"))
    if "import_key" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN import_key VARCHAR(64)"))
    if "source_file_checksum" not in demo_cols:
        await session.execute(text("ALTER TABLE demos ADD COLUMN source_file_checksum VARCHAR(64)"))

    # Follow-ups columns
    res_fu = await session.execute(text("PRAGMA table_info(follow_ups)"))
    fu_cols = {row[1] for row in res_fu.fetchall()}
    if "company_id" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN company_id CHAR(32)"))
    if "next_step" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN next_step TEXT"))
    if "source_sheet" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN source_sheet VARCHAR(50)"))
    if "source_row" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN source_row INTEGER"))
    if "company_name_snapshot" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN company_name_snapshot VARCHAR(500)"))
    if "meeting_with" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN meeting_with VARCHAR(255)"))
    if "demo_id" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN demo_id CHAR(32)"))
    if "import_key" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN import_key VARCHAR(64)"))
    if "source_file_checksum" not in fu_cols:
        await session.execute(text("ALTER TABLE follow_ups ADD COLUMN source_file_checksum VARCHAR(64)"))

    # Tasks columns (req 12 archive support)
    res_tasks = await session.execute(text("PRAGMA table_info(tasks)"))
    task_cols = {row[1] for row in res_tasks.fetchall()}
    if "archived_at" not in task_cols:
        await session.execute(text("ALTER TABLE tasks ADD COLUMN archived_at DATETIME"))
    if "archived_by" not in task_cols:
        await session.execute(text("ALTER TABLE tasks ADD COLUMN archived_by CHAR(32)"))

    # Opportunities columns
    res_opps = await session.execute(text("PRAGMA table_info(opportunities)"))
    opp_cols = {row[1] for row in res_opps.fetchall()}
    if "company_name_snapshot" not in opp_cols:
        await session.execute(text("ALTER TABLE opportunities ADD COLUMN company_name_snapshot VARCHAR(500)"))
    if "contact_person" not in opp_cols:
        await session.execute(text("ALTER TABLE opportunities ADD COLUMN contact_person VARCHAR(255)"))
    if "notes" not in opp_cols:
        await session.execute(text("ALTER TABLE opportunities ADD COLUMN notes TEXT"))
    if "next_step" not in opp_cols:
        await session.execute(text("ALTER TABLE opportunities ADD COLUMN next_step TEXT"))

    # Leads archive table
    await session.execute(text("""
    CREATE TABLE IF NOT EXISTS leads_archive (
        id CHAR(32) PRIMARY KEY,
        batch_id VARCHAR(100) NOT NULL,
        sheet_name VARCHAR(100) NOT NULL DEFAULT 'Leads',
        row_number INTEGER NOT NULL,
        raw_data TEXT NOT NULL,
        name VARCHAR(255),
        company_name VARCHAR(255),
        position VARCHAR(255),
        phone VARCHAR(100),
        email VARCHAR(255),
        salesperson VARCHAR(100),
        row_checksum VARCHAR(64),
        archived_at DATETIME NOT NULL
    )
    """))

    # Same backfill as the PostgreSQL path. An empty `cols` means there is no users
    # table yet, in which case the ALTERs above would have failed and there is
    # nothing to backfill.
    if cols:
        await _backfill_pre_verification_accounts(session)


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
