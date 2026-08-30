import sqlite3
conn = sqlite3.connect('crm.db')
c = conn.cursor()

c.execute("""
    SELECT u.first_name, ct.status, COUNT(*) as cnt
    FROM contacts ct
    LEFT JOIN users u ON ct.owner_id = u.id
    WHERE ct.status = 'PENDING_CLAIM' AND ct.deleted_at IS NULL
    GROUP BY ct.owner_id, u.first_name, ct.status
""")
for r in c.fetchall():
    print("PENDING_CLAIM group:", r)

c.execute("SELECT id FROM users WHERE first_name='Saleh' LIMIT 1")
saleh_id = c.fetchone()[0]
print("Saleh DB id:", saleh_id)

c.execute("SELECT COUNT(*) FROM contacts WHERE status='PENDING_CLAIM' AND deleted_at IS NULL")
print("Total PENDING_CLAIM:", c.fetchone()[0])

# Check format of owner_id in PENDING_CLAIM contacts vs Saleh's id
c.execute("SELECT id, owner_id FROM contacts WHERE status='PENDING_CLAIM' LIMIT 3")
for r in c.fetchall():
    print("Contact:", r[0], "| owner_id:", r[1])

conn.close()
