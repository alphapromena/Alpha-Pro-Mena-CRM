import sqlite3

conn = sqlite3.connect('f:/New folder/backend/crm.db')
cur = conn.cursor()
cur.execute('SELECT count(*) FROM contacts WHERE deleted_at IS NULL')
print('Total active contacts in DB:', cur.fetchone()[0])
cur.execute('''
SELECT coalesce(u.first_name, 'Unassigned'), coalesce(u.email, '-'), count(c.id) 
FROM contacts c 
LEFT JOIN users u ON c.owner_id = u.id 
WHERE c.deleted_at IS NULL 
GROUP BY u.id 
ORDER BY count(c.id) DESC
''')
for r in cur.fetchall():
    print(f"  {r[0]:<15} {r[1]:<28} : {r[2]} leads")
conn.close()
