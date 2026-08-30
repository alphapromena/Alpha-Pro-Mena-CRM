"""
add_sheet_order_migration.py

Adds `sheet_order` column to the contacts table (SQLite compatible) and
backfills it for all existing contacts using their created_at order.

Run once from the backend/ directory:
    python -m app.add_sheet_order_migration

Safe to run multiple times.
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def run():
    async with engine.begin() as conn:
        # 1. Check if column already exists (SQLite: PRAGMA table_info)
        check_result = await conn.execute(text("PRAGMA table_info(contacts)"))
        columns = {row[1] for row in check_result.fetchall()}

        if "sheet_order" in columns:
            print("Column 'sheet_order' already exists on contacts table. Skipping DDL.")
        else:
            print("Adding 'sheet_order' column to contacts table...")
            await conn.execute(text(
                "ALTER TABLE contacts ADD COLUMN sheet_order INTEGER DEFAULT NULL"
            ))
            # SQLite doesn't support CREATE INDEX in same transaction easily but it works
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_contacts_sheet_order ON contacts (sheet_order)"
            ))
            print("Column added.")

        # 2. Backfill: assign sequential values ordered by created_at
        # SQLite doesn't have ROW_NUMBER() in older versions, so we use a subquery trick.
        print("Backfilling sheet_order for contacts where sheet_order IS NULL...")

        # Fetch IDs in order
        id_result = await conn.execute(text("""
            SELECT id
            FROM contacts
            WHERE deleted_at IS NULL
              AND sheet_order IS NULL
            ORDER BY created_at ASC, id ASC
        """))
        ids = [row[0] for row in id_result.fetchall()]

        if ids:
            # Assign sequential values starting from max existing + 1
            max_result = await conn.execute(text(
                "SELECT COALESCE(MAX(sheet_order), 0) FROM contacts"
            ))
            start = (max_result.scalar_one() or 0) + 1

            for i, contact_id in enumerate(ids):
                await conn.execute(text(
                    "UPDATE contacts SET sheet_order = :order WHERE id = :id"
                ), {"order": start + i, "id": contact_id})

            print(f"Backfill complete. {len(ids)} contacts now have sheet_order set (starting at {start}).")
        else:
            print("No contacts needed backfill (all already have sheet_order).")

    print("Migration finished successfully.")


if __name__ == "__main__":
    asyncio.run(run())
