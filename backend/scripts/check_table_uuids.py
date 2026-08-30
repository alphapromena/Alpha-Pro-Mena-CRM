import sqlite3

conn = sqlite3.connect('crm.db')
c = conn.cursor()

# Check sample IDs from various tables
for table in ['users', 'contacts', 'companies', 'calls', 'tasks']:
    c.execute(f"SELECT id FROM {table} LIMIT 3")
    rows = c.fetchall()
    print(f"Table '{table}' ID format:")
    for r in rows:
        val = r[0]
        print(f"  len={len(val)}: {val}")

conn.close()
