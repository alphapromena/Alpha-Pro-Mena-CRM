import sqlite3
conn = sqlite3.connect('crm.db')
c = conn.cursor()
# Check UUID format for null-owner contacts
c.execute('SELECT id, owner_id, status FROM contacts WHERE owner_id IS NULL LIMIT 3')
for r in c.fetchall():
    print('id:', repr(r[0]), '| owner:', repr(r[1]), '| status:', repr(r[2]))
print()
# Check existing Saleh contacts
c.execute("SELECT id FROM contacts WHERE status='NEW' LIMIT 2")
for r in c.fetchall():
    print('existing NEW id:', repr(r[0]))
conn.close()
