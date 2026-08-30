import sqlite3
conn = sqlite3.connect('crm.db')
c = conn.cursor()
c.execute("SELECT status, COUNT(*) FROM contacts WHERE deleted_at IS NULL GROUP BY status ORDER BY status")
for r in c.fetchall():
    print(r)
print()
c.execute("SELECT COUNT(*) FROM contacts WHERE owner_id IS NULL AND status != 'ARCHIVED' AND deleted_at IS NULL")
print("Unassigned active leads:", c.fetchone()[0])
conn.close()
