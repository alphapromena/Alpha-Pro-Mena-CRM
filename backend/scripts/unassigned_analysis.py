"""
Unassigned contacts analysis script.
Reports which contacts have no owner (owner_id IS NULL) and their source sheets,
with sample data to help decide how to reassign them.
"""
import sqlite3

conn = sqlite3.connect('crm.db')
c = conn.cursor()

print("=" * 70)
print("UNASSIGNED CONTACTS ANALYSIS")
print("=" * 70)

# Total unassigned
c.execute(
    "SELECT COUNT(*) FROM contacts WHERE owner_id IS NULL AND deleted_at IS NULL"
)
total_unassigned = c.fetchone()[0]
print(f"Total unassigned contacts: {total_unassigned}")

# By source sheet
print("\nUnassigned by source sheet:")
c.execute(
    "SELECT source_sheet, status, COUNT(*) as cnt "
    "FROM contacts WHERE owner_id IS NULL AND deleted_at IS NULL "
    "GROUP BY source_sheet, status ORDER BY source_sheet, cnt DESC"
)
for row in c.fetchall():
    print(f"  {row[0] or '(no sheet)'} | {row[1]} | {row[2]} contacts")

# By status
print("\nUnassigned by status:")
c.execute(
    "SELECT status, COUNT(*) as cnt FROM contacts "
    "WHERE owner_id IS NULL AND deleted_at IS NULL "
    "GROUP BY status ORDER BY cnt DESC"
)
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Sample of unassigned UNASSIGNED status contacts
print("\nSample unassigned contacts (first 10, UNASSIGNED status):")
c.execute(
    "SELECT id, first_name, last_name, phone, company_id, source_sheet "
    "FROM contacts WHERE owner_id IS NULL AND deleted_at IS NULL "
    "AND status = 'UNASSIGNED' LIMIT 10"
)
for row in c.fetchall():
    print(f"  {row[1]} {row[2]} | {row[3]} | sheet: {row[5]}")

# Check if any unassigned contacts were from Gulf workbook (Sheet16)
print("\nUnassigned from Sheet16 (Gulf workbook):")
c.execute(
    "SELECT COUNT(*) FROM contacts WHERE owner_id IS NULL AND deleted_at IS NULL "
    "AND source_sheet = 'Sheet16'"
)
sheet16_unassigned = c.fetchone()[0]
print(f"  Sheet16 unassigned: {sheet16_unassigned}")

# All Sheet16 contacts
print("\nAll Sheet16 contacts by owner:")
c.execute(
    "SELECT u.first_name, COUNT(ct.id) as cnt "
    "FROM contacts ct "
    "LEFT JOIN users u ON ct.owner_id = u.id "
    "WHERE ct.source_sheet = 'Sheet16' AND ct.deleted_at IS NULL "
    "GROUP BY ct.owner_id ORDER BY u.first_name"
)
for row in c.fetchall():
    print(f"  {row[0] or '(unassigned)'}: {row[1]}")

# Check DEMO_SCHEDULED contacts with no owner
print("\nDEMO_SCHEDULED contacts with no owner:")
c.execute(
    "SELECT first_name, last_name, phone, company_id FROM contacts "
    "WHERE owner_id IS NULL AND deleted_at IS NULL AND status = 'DEMO_SCHEDULED'"
)
for row in c.fetchall():
    print(f"  {row[0]} {row[1]} | {row[2]}")

conn.close()
print("\nDone.")
