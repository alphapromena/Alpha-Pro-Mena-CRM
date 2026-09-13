"""Detailed Hassan contact analysis."""
import sqlite3

conn = sqlite3.connect('crm.db')
c = conn.cursor()

hassan_id = '595d3a7341c54cfc82b25094f6d0268e'

# Check all statuses including archived
c.execute(
    'SELECT status, archived_at IS NOT NULL as is_archived, COUNT(*) '
    'FROM contacts WHERE owner_id=? AND deleted_at IS NULL '
    'GROUP BY status, is_archived ORDER BY status',
    (hassan_id,)
)
print('Hassan contacts by status + archived flag:')
for row in c.fetchall():
    print(row)

# Verify the specific ACTIVE (not archived) count Hassan should see
c.execute(
    'SELECT COUNT(*) FROM contacts WHERE owner_id=? AND deleted_at IS NULL '
    'AND status NOT IN ("ARCHIVED","PENDING_CLAIM") AND archived_at IS NULL',
    (hassan_id,)
)
print('\nHassan active contacts (what list_contacts returns):', c.fetchone()[0])

# Contacts with PENDING_CLAIM or ARCHIVED (should be 0 for hassan?)
c.execute(
    'SELECT status, COUNT(*) FROM contacts WHERE owner_id=? AND deleted_at IS NULL '
    'AND status IN ("ARCHIVED","PENDING_CLAIM") GROUP BY status',
    (hassan_id,)
)
print('\nHassan archived/pending_claim contacts:')
for row in c.fetchall():
    print(row)

# Saleh counts
saleh_id = '0e48de67d8a049eba3e1bfed5ffc3d1c'
c.execute(
    'SELECT COUNT(*) FROM contacts WHERE owner_id=? AND deleted_at IS NULL '
    'AND status NOT IN ("ARCHIVED","PENDING_CLAIM") AND archived_at IS NULL',
    (saleh_id,)
)
print('\nSaleh active contacts:', c.fetchone()[0])

# Amin counts
amin_id = 'f25f135e590b436997a0362f759dcfb8'
c.execute(
    'SELECT COUNT(*) FROM contacts WHERE owner_id=? AND deleted_at IS NULL '
    'AND status NOT IN ("ARCHIVED","PENDING_CLAIM") AND archived_at IS NULL',
    (amin_id,)
)
print('Amin active contacts:', c.fetchone()[0])

# Ghaida counts
ghaida_id = '1caed1fe420643798e989eb42d478cea'
c.execute(
    'SELECT COUNT(*) FROM contacts WHERE owner_id=? AND deleted_at IS NULL '
    'AND status NOT IN ("ARCHIVED","PENDING_CLAIM") AND archived_at IS NULL',
    (ghaida_id,)
)
print('Ghaida active contacts:', c.fetchone()[0])

# Look at the leads page context - how are contacts returned?
# Check if there are special status values that block visibility
c.execute('SELECT DISTINCT status FROM contacts WHERE deleted_at IS NULL')
print('\nAll distinct status values in contacts:')
for row in c.fetchall():
    print(row[0])

conn.close()
