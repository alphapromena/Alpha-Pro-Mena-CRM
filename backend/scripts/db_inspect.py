"""DB inspection script for production diagnostics."""
import sqlite3

conn = sqlite3.connect('crm.db')
c = conn.cursor()

print("=== USERS ===")
c.execute('SELECT id, first_name, email, role, is_active FROM users ORDER BY first_name')
for row in c.fetchall():
    print(row)

print("\n=== CONTACT COUNT PER OWNER (non-deleted, non-archived, non-pending_claim) ===")
c.execute(
    "SELECT u.first_name, COUNT(ct.id) as cnt "
    "FROM contacts ct "
    "LEFT JOIN users u ON ct.owner_id = u.id "
    "WHERE ct.deleted_at IS NULL AND ct.status NOT IN ('ARCHIVED', 'PENDING_CLAIM') "
    "GROUP BY ct.owner_id ORDER BY u.first_name"
)
for row in c.fetchall():
    print(row)

print("\n=== CONTACT COUNT INCLUDING ARCHIVED (non-deleted) per owner ===")
c.execute(
    "SELECT u.first_name, COUNT(ct.id) as cnt "
    "FROM contacts ct "
    "LEFT JOIN users u ON ct.owner_id = u.id "
    "WHERE ct.deleted_at IS NULL "
    "GROUP BY ct.owner_id ORDER BY u.first_name"
)
for row in c.fetchall():
    print(row)

print("\n=== TOTAL CONTACTS ===")
c.execute("SELECT COUNT(*) FROM contacts WHERE deleted_at IS NULL")
print("Total (not deleted):", c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM contacts")
print("Total (all):", c.fetchone()[0])

print("\n=== CONTACTS WITH NO OWNER (unassigned) ===")
c.execute(
    "SELECT COUNT(*) FROM contacts WHERE owner_id IS NULL AND deleted_at IS NULL"
)
print("Unassigned:", c.fetchone()[0])

print("\n=== COMPANIES ===")
c.execute("SELECT COUNT(*) FROM companies WHERE deleted_at IS NULL")
print("Total companies:", c.fetchone()[0])

print("\n=== CONTACTS STATUS BREAKDOWN FOR HASSAN ===")
hassan_id = "595d3a7341c54cfc82b25094f6d0268e"
c.execute(
    "SELECT status, COUNT(*) FROM contacts WHERE owner_id=? AND deleted_at IS NULL GROUP BY status",
    (hassan_id,)
)
for row in c.fetchall():
    print(row)

print("\n=== CONTACT SAMPLE FOR HASSAN (first 10) ===")
c.execute(
    "SELECT id, first_name, last_name, phone, status, company_id FROM contacts WHERE owner_id=? AND deleted_at IS NULL LIMIT 10",
    (hassan_id,)
)
for row in c.fetchall():
    print(row)

print("\n=== SHEET SOURCES FOUND IN CONTACTS ===")
c.execute("SELECT DISTINCT source_sheet FROM contacts WHERE source_sheet IS NOT NULL LIMIT 30")
for row in c.fetchall():
    print(row)

print("\n=== IMPORT KEYS SAMPLE ===")
c.execute("SELECT import_key FROM contacts WHERE import_key IS NOT NULL LIMIT 10")
for row in c.fetchall():
    print(row)

conn.close()
