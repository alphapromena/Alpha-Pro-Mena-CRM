import sqlite3

conn = sqlite3.connect('crm.db')
c = conn.cursor()

# Find any table/column that contains hyphens in ID / foreign key fields
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [r[0] for r in c.fetchall()]

print("Normalizing UUID columns across all tables to 32-character hex...")

for table in tables:
    c.execute(f"PRAGMA table_info({table})")
    cols = c.fetchall()
    for col in cols:
        col_name = col[1]
        col_type = col[2]
        if col_name == 'id' or col_name.endswith('_id') or 'uuid' in col_name.lower():
            # Check if this column has values with hyphens
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE {col_name} LIKE '%-%'")
            hyphen_count = c.fetchone()[0]
            if hyphen_count > 0:
                print(f"Table '{table}', Column '{col_name}': {hyphen_count} rows with hyphens. Updating to hex (no hyphens)...")
                c.execute(f"UPDATE {table} SET {col_name} = REPLACE({col_name}, '-', '') WHERE {col_name} LIKE '%-%'")
                conn.commit()
                print(f"  -> Done.")

# Verify contacts.id format now
c.execute("SELECT id FROM contacts LIMIT 5")
print("\nSample contacts.id after update:")
for r in c.fetchall():
    print(f"  len={len(r[0])}: {r[0]}")

conn.close()
print("\n[OK] UUID normalization complete.")
