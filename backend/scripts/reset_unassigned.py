import sqlite3
conn = sqlite3.connect('crm.db')
c = conn.cursor()
c.execute("UPDATE contacts SET owner_id = NULL, status = 'UNASSIGNED' WHERE status = 'PENDING_CLAIM'")
conn.commit()
print("Reset PENDING_CLAIM contacts:", c.rowcount)
conn.close()
