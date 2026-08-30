"""
Repair integrity problems in an existing CRM database (SQLite or PostgreSQL).

    cd backend
    .venv\Scripts\python -m scripts.fix_db_integrity            # dry run: report only
    .venv\Scripts\python -m scripts.fix_db_integrity --apply    # execute (SQLite file is backed up first)

What it fixes (all found in the 2026-08-30 audit):
  1. Child rows whose parent contact no longer exists (lead_assignments, demos,
     opportunities + roadmap steps) - leftovers of hard-deleted test data.
  2. User references pointing at users that no longer exist -> NULL
     (teams.manager_id, automation_rules.created_by, campaigns.owner_id,
      audit_logs.actor_id, google_sheets_sync_configs.created_by, lead_assignments.*,
      demos.owner_id, opportunities.owner_id).
  3. "Test Idempotent Sheet" sync configs (spreadsheet_id LIKE 'test_%') and their runs,
     which the scheduler was re-syncing every 15 minutes.
  4. The legacy auto-created account qusai@alphapro.com -> deactivated + soft-deleted.
  5. Duplicate indexes idx_contacts_normalized_email / _phone (the model keeps ix_*).
"""
import argparse
import asyncio
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.config import get_settings
from app.database import engine

settings = get_settings()

MISSING_USER = "{col} IS NOT NULL AND {col} NOT IN (SELECT id FROM users)"
MISSING_CONTACT = "contact_id IS NOT NULL AND contact_id NOT IN (SELECT id FROM contacts)"

# (label, table, where-clause, action)  action: DELETE | NULL:<column>
STEPS = [
    ("orphan lead_assignments", "lead_assignments", MISSING_CONTACT, "DELETE"),
    ("orphan demos", "demos", MISSING_CONTACT, "DELETE"),
    ("roadmap steps of orphan opportunities", "opportunity_roadmap_steps",
     "opportunity_id IN (SELECT id FROM opportunities WHERE " + MISSING_CONTACT + ")", "DELETE"),
    ("orphan opportunities", "opportunities", MISSING_CONTACT, "DELETE"),
] + [
    (f"dangling {t}.{c}", t, MISSING_USER.format(col=c), f"NULL:{c}")
    for t, c in [
        ("teams", "manager_id"), ("automation_rules", "created_by"), ("campaigns", "owner_id"),
        ("audit_logs", "actor_id"), ("google_sheets_sync_configs", "created_by"),
        ("lead_assignments", "assigned_by"), ("lead_assignments", "assigned_to"),
        ("lead_assignments", "previous_owner_id"), ("demos", "owner_id"), ("opportunities", "owner_id"),
    ]
] + [
    ("test sync runs", "google_sheets_sync_runs",
     "config_id IN (SELECT id FROM google_sheets_sync_configs WHERE spreadsheet_id LIKE 'test_%')", "DELETE"),
    ("test sync configs", "google_sheets_sync_configs", "spreadsheet_id LIKE 'test_%'", "DELETE"),
]

LEGACY_ACCOUNT = "qusai@alphapro.com"
DUPLICATE_INDEXES = ("idx_contacts_normalized_email", "idx_contacts_normalized_phone")


def backup_sqlite() -> Path | None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        return None
    src = Path(url.split(":///", 1)[1])
    dest = src.parent / "backups" / f"{src.stem}-{datetime.now():%Y%m%d-%H%M%S}-pre-fix{src.suffix}"
    dest.parent.mkdir(exist_ok=True)
    shutil.copy2(src, dest)
    return dest


async def run(apply: bool) -> None:
    mode = "APPLY" if apply else "DRY RUN"
    print(f"[{mode}] database: {settings.database_url}")
    if apply:
        backup = backup_sqlite()
        if backup:
            print(f"backup written: {backup}")

    async with engine.begin() as conn:
        for label, table, where, action in STEPS:
            count = (await conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"))).scalar_one()
            print(f"  {label:<50} {count:>5} row(s)")
            if apply and count:
                if action == "DELETE":
                    await conn.execute(text(f"DELETE FROM {table} WHERE {where}"))
                else:
                    col = action.split(":", 1)[1]
                    await conn.execute(text(f"UPDATE {table} SET {col} = NULL WHERE {where}"))

        legacy = (await conn.execute(
            text("SELECT COUNT(*) FROM users WHERE email = :e AND deleted_at IS NULL"), {"e": LEGACY_ACCOUNT}
        )).scalar_one()
        print(f"  {'legacy account ' + LEGACY_ACCOUNT:<50} {legacy:>5} row(s)")
        if apply and legacy:
            await conn.execute(text(
                "UPDATE users SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                "WHERE email = :e AND deleted_at IS NULL"
            ), {"e": LEGACY_ACCOUNT})

        for idx in DUPLICATE_INDEXES:
            print(f"  {'drop duplicate index ' + idx:<50}  {'(apply)' if apply else '(planned)'}")
            if apply:
                await conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))

    if apply and settings.database_url.startswith("sqlite"):
        async with engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text("VACUUM"))
            violations = (await conn.execute(text("PRAGMA foreign_key_check"))).fetchall()
            print(f"remaining foreign-key violations: {len(violations)}")
    await engine.dispose()
    print("done." if apply else "dry run complete - re-run with --apply to execute.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="execute the changes (default is dry run)")
    asyncio.run(run(parser.parse_args().apply))
