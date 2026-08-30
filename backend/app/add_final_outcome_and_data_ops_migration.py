"""
Migration script:
1. Adds final_outcome, archived_at, and archived_by_id columns to contacts table if missing.
2. Updates Aseel's role to DATA_OPS.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "crm.db")

def run_migration():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Check existing columns in contacts table
    cur.execute("PRAGMA table_info(contacts);")
    columns = [row[1] for row in cur.fetchall()]
    print(f"Existing columns in contacts: {len(columns)} columns found.")

    if "final_outcome" not in columns:
        print("Adding column 'final_outcome' to contacts...")
        cur.execute("ALTER TABLE contacts ADD COLUMN final_outcome VARCHAR(50);")
    else:
        print("Column 'final_outcome' already exists.")

    if "archived_at" not in columns:
        print("Adding column 'archived_at' to contacts...")
        cur.execute("ALTER TABLE contacts ADD COLUMN archived_at TIMESTAMP;")
    else:
        print("Column 'archived_at' already exists.")

    if "archived_by_id" not in columns:
        print("Adding column 'archived_by_id' to contacts...")
        cur.execute("ALTER TABLE contacts ADD COLUMN archived_by_id CHAR(32);")
    else:
        print("Column 'archived_by_id' already exists.")

    # Create index on final_outcome and archived_at
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contacts_final_outcome ON contacts(final_outcome);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contacts_archived_at ON contacts(archived_at);")

    # 2. Update Aseel's account to DATA_OPS
    cur.execute("SELECT id, first_name, email, role FROM users WHERE email LIKE '%aseel%';")
    aseel_rows = cur.fetchall()
    if aseel_rows:
        for r in aseel_rows:
            print(f"Updating Aseel user ({r[0]}, {r[1]}, {r[2]}) from '{r[3]}' to 'DATA_OPS'...")
            cur.execute("UPDATE users SET role = 'DATA_OPS' WHERE id = ?;", (r[0],))
    else:
        print("Aseel user not found in DB.")

    conn.commit()
    print("Migration completed successfully!")

    # Verify
    cur.execute("PRAGMA table_info(contacts);")
    new_cols = [row[1] for row in cur.fetchall()]
    print(f"Updated columns in contacts ({len(new_cols)} total): final_outcome={'final_outcome' in new_cols}, archived_at={'archived_at' in new_cols}, archived_by_id={'archived_by_id' in new_cols}")

    cur.execute("SELECT id, first_name, email, role FROM users WHERE email LIKE '%aseel%';")
    print(f"Aseel in DB: {cur.fetchall()}")

    conn.close()

if __name__ == "__main__":
    run_migration()
