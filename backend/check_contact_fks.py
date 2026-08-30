import sqlite3

conn = sqlite3.connect('crm.db')
c = conn.cursor()

for table in ['tasks', 'calls', 'lead_assignments', 'contact_notes', 'contact_timeline', 'opportunities']:
    try:
        c.execute(f"SELECT contact_id FROM {table} WHERE contact_id IS NOT NULL LIMIT 5")
        rows = c.fetchall()
        print(f"Table '{table}' contact_id:")
        for r in rows:
            print(f"  len={len(r[0]) if r[0] else 0}: {r[0]}")
    except Exception as e:
        print(f"Table '{table}': {e}")

conn.close()
