import sqlite3

conn = sqlite3.connect('crm.db')
c = conn.cursor()

c.execute("SELECT id, company_id, owner_id FROM contacts WHERE owner_id IS NOT NULL LIMIT 5")
for r in c.fetchall():
    print(f"contact.id: len={len(r[0]) if r[0] else 0} {r[0]} | company_id: len={len(r[1]) if r[1] else 0} {r[1]} | owner_id: len={len(r[2]) if r[2] else 0} {r[2]}")

conn.close()
