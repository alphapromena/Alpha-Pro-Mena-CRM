import sqlite3

DB = 'f:\\New folder\\backend\\crm.db'
conn = sqlite3.connect(DB)
c = conn.cursor()

# Check users - first_name + last_name
c.execute("SELECT id, first_name, last_name, email, role FROM users WHERE deleted_at IS NULL ORDER BY first_name")
print('=== USERS ===')
for row in c.fetchall():
    print(f'  id={row[0]} | {row[1]} {row[2]} | {row[3]} | {row[4]}')

print()

# Count active contacts by owner
c.execute("""
SELECT u.first_name || ' ' || u.last_name, COUNT(*) 
FROM contacts ct
JOIN users u ON ct.owner_id = u.id
WHERE ct.status != 'ARCHIVED'
GROUP BY ct.owner_id
ORDER BY u.first_name
""")
print('=== ACTIVE CONTACTS BY REP ===')
total_active = 0
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')
    total_active += row[1]

c.execute("SELECT COUNT(*) FROM contacts WHERE status = 'UNASSIGNED'")
unassigned = c.fetchone()[0]
print(f'  Unassigned: {unassigned}')
print(f'  TOTAL ACTIVE+UNASSIGNED: {total_active + unassigned}')

print()

# Count archived contacts by owner
c.execute("""
SELECT u.first_name || ' ' || u.last_name, COUNT(*) 
FROM contacts ct
JOIN users u ON ct.owner_id = u.id
WHERE ct.status = 'ARCHIVED'
GROUP BY ct.owner_id
ORDER BY u.first_name
""")
print('=== ARCHIVED CONTACTS BY REP ===')
total_arch = 0
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')
    total_arch += row[1]
print(f'  TOTAL ARCHIVED: {total_arch}')

print()

# Check source_sheet values
c.execute("SELECT source_sheet, status, COUNT(*) FROM contacts GROUP BY source_sheet, status ORDER BY source_sheet, status")
print('=== BY SOURCE SHEET + STATUS ===')
for row in c.fetchall():
    print(f'  sheet={repr(row[0])} | status={row[1]}: {row[2]}')

print()

# Check fake data in ARCHIVED contacts  
c.execute("SELECT COUNT(*) FROM contacts WHERE (first_name || ' ' || last_name) LIKE 'Contact_0%' AND status = 'ARCHIVED'")
print(f'Archived fake contact_0 records: {c.fetchone()[0]}')
c.execute("SELECT COUNT(*) FROM contacts WHERE email LIKE '%@elmtest.sa' AND status = 'ARCHIVED'")
print(f'Archived fake elmtest.sa emails: {c.fetchone()[0]}')
c.execute("SELECT COUNT(*) FROM contacts WHERE phone = '+966580000000' AND status = 'ARCHIVED'")
print(f'Archived fake 966580000000 phones: {c.fetchone()[0]}')

print()

# Sample first 10 archived contacts
c.execute("""
SELECT ct.first_name || ' ' || ct.last_name, ct.phone, ct.email, ct.company_id, u.first_name, ct.source_sheet, ct.sheet_order
FROM contacts ct
LEFT JOIN users u ON ct.owner_id = u.id
WHERE ct.status = 'ARCHIVED'
ORDER BY ct.sheet_order ASC
LIMIT 10
""")
print('=== FIRST 10 ARCHIVED (by sheet_order) ===')
for row in c.fetchall():
    email_short = (row[2][:40] if row[2] else '')
    print(f'  order={row[6]} | rep={row[4]} | name={row[0]} | phone={row[1]} | email={email_short}')

print()

# Sample first 10 active contacts
c.execute("""
SELECT ct.first_name || ' ' || ct.last_name, ct.phone, ct.email, ct.company_id, u.first_name, ct.source_sheet, ct.sheet_order
FROM contacts ct
LEFT JOIN users u ON ct.owner_id = u.id
WHERE ct.status != 'ARCHIVED'
ORDER BY ct.sheet_order ASC
LIMIT 10
""")
print('=== FIRST 10 ACTIVE (by sheet_order) ===')
for row in c.fetchall():
    email_short = (row[2][:40] if row[2] else '')
    print(f'  order={row[6]} | rep={row[4]} | name={row[0]} | phone={row[1]} | email={email_short}')

conn.close()
