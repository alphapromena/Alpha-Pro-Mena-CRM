"""
FIX ATTEMPT HISTORY
====================
The reimport_crm_active.py script did not import attempt columns (6, 7, 8).
This script:
  1. Removes any leftover duplicate contacts (older import with different sheet_order)
  2. Updates every active contact's attempt_1/attempt_2/attempt_3 from CRM.xlsx
  3. Also updates attempt_count to reflect real number
"""
import sqlite3
import openpyxl
import re
from datetime import datetime, timezone
from collections import defaultdict

DB_PATH = 'f:\\New folder\\backend\\crm.db'
CRM_PATH = 'f:\\New folder\\CRM.xlsx'

def normalize_phone(phone):
    if not phone:
        return None
    p = re.sub(r'[^\d+]', '', str(phone).strip())
    return p if len(p) >= 7 else None

def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print("FIX ATTEMPT HISTORY IMPORT")
    print("=" * 70)

    # ── STEP 1: Identify and remove duplicate contacts ────────────────────────
    # The current clean import has sheet_order = original Excel row (118-840 for Saleh, etc.)
    # The old duplicates have large sheet_order values (>1800) from previous imports
    # They are identified by sheet_order > 1801 (beyond the real CRM.xlsx row count)
    print("\n[1] Checking for stale duplicate contacts...")
    c.execute("""
        SELECT id, first_name, last_name, phone, sheet_order, owner_id
        FROM contacts
        WHERE status = 'NEW'
          AND deleted_at IS NULL
          AND sheet_order > 1801
    """)
    stale_dupes = c.fetchall()
    print(f"  Stale contacts with sheet_order > 1801: {len(stale_dupes)}")
    
    if stale_dupes:
        stale_ids = [r['id'] for r in stale_dupes[:5]]
        print(f"  Samples: {[(r['first_name'], r['last_name'], r['sheet_order']) for r in stale_dupes[:5]]}")
        # Delete all stale dupes
        chunk = [r['id'] for r in stale_dupes]
        ph = ','.join('?' * len(chunk))
        c.execute(f"DELETE FROM contacts WHERE id IN ({ph})", chunk)
        print(f"  Deleted {c.rowcount} stale duplicate contacts")
        conn.commit()

    # ── STEP 2: Load CRM.xlsx and build attempt map keyed by row index ────────
    print("\n[2] Loading CRM.xlsx attempt data...")
    wb = openpyxl.load_workbook(CRM_PATH, read_only=True, data_only=True)
    ws = wb['Sheet1']

    # Map: sheet_row_index -> {attempt_1, attempt_2, attempt_3}
    attempt_map = {}  # key = row_idx (1-based)
    
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if all(v is None for v in row):
            continue
        a1 = str(row[6]).strip() if len(row) > 6 and row[6] is not None else None
        a2 = str(row[7]).strip() if len(row) > 7 and row[7] is not None else None
        a3 = str(row[8]).strip() if len(row) > 8 and row[8] is not None else None
        # Only store if at least one attempt exists
        if a1 or a2 or a3:
            attempt_map[row_idx] = {
                'attempt_1': a1 if a1 else None,
                'attempt_2': a2 if a2 else None,
                'attempt_3': a3 if a3 else None,
            }

    wb.close()
    print(f"  Rows with attempt data: {len(attempt_map)}")

    # ── STEP 3: Update each active contact with attempt data from source ───────
    print("\n[3] Updating active contacts with attempt history...")
    
    c.execute("""
        SELECT id, first_name, last_name, sheet_order
        FROM contacts
        WHERE status = 'NEW'
          AND deleted_at IS NULL
        ORDER BY sheet_order ASC
    """)
    active_contacts = c.fetchall()
    print(f"  Active contacts to process: {len(active_contacts)}")

    updated = 0
    skipped_no_data = 0
    skipped_no_row = 0

    for contact in active_contacts:
        sheet_order = contact['sheet_order']
        if sheet_order is None:
            skipped_no_row += 1
            continue

        attempts = attempt_map.get(sheet_order)
        if not attempts:
            skipped_no_data += 1
            continue

        a1 = attempts['attempt_1']
        a2 = attempts['attempt_2']
        a3 = attempts['attempt_3']
        # Count non-None attempts
        count = sum(1 for a in [a1, a2, a3] if a)

        c.execute("""
            UPDATE contacts
            SET attempt_1=?, attempt_2=?, attempt_3=?, attempt_count=?, updated_at=?
            WHERE id=?
        """, (a1, a2, a3, count, now, contact['id']))
        updated += 1

    conn.commit()
    print(f"  Updated:              {updated}")
    print(f"  No attempt data:      {skipped_no_data} (legitimately blank in source)")
    print(f"  No sheet_order:       {skipped_no_row}")

    # ── STEP 4: Verify the named stc Bank contacts ────────────────────────────
    print("\n[4] Verifying named stc Bank contacts...")
    names = [('Ayman', 'Ali'), ('Raghad', 'Alhammad'), ('Yousif', 'Elamin')]
    for first, last in names:
        c.execute("""
            SELECT first_name, last_name, phone, attempt_1, attempt_2, attempt_3, attempt_count, sheet_order
            FROM contacts
            WHERE first_name=? AND last_name=? AND status='NEW' AND deleted_at IS NULL
        """, (first, last))
        rows = c.fetchall()
        if not rows:
            print(f"  {first} {last}: NOT FOUND")
        for r in rows:
            print(f"  {r['first_name']} {r['last_name']} (row {r['sheet_order']}): "
                  f"A1={r['attempt_1']!r} | A2={r['attempt_2']!r} | A3={r['attempt_3']!r} | count={r['attempt_count']}")

    # ── STEP 5: Final broad verification ──────────────────────────────────────
    print("\n[5] Final attempt coverage by rep:")
    c.execute("""
        SELECT u.first_name as owner,
               COUNT(*) as total,
               SUM(CASE WHEN attempt_1 IS NOT NULL AND attempt_1 != '' THEN 1 ELSE 0 END) as has_a1,
               SUM(CASE WHEN attempt_1 IS NULL OR attempt_1 = '' THEN 1 ELSE 0 END) as blank_a1
        FROM contacts ct
        LEFT JOIN users u ON ct.owner_id = u.id
        WHERE ct.status = 'NEW' AND ct.deleted_at IS NULL
        GROUP BY ct.owner_id, u.first_name
        ORDER BY u.first_name
    """)
    print(f"  {'Owner':<12} {'Total':<8} {'Has A1':<10} {'Blank A1':<10} {'Coverage'}")
    print("  " + "-" * 55)
    for r in c.fetchall():
        total = r['total']
        has = r['has_a1']
        blank = r['blank_a1']
        pct = f"{100*has//total}%" if total else "0%"
        print(f"  {r['owner'] or 'Unknown':<12} {total:<8} {has:<10} {blank:<10} {pct}")

    # Check duplicate count now
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='NEW' AND deleted_at IS NULL")
    new_total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='UNASSIGNED' AND deleted_at IS NULL")
    unassigned = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='ARCHIVED' AND deleted_at IS NULL")
    archived = c.fetchone()[0]
    print(f"\n  Active (NEW): {new_total}")
    print(f"  Unassigned:   {unassigned}")
    print(f"  Archived:     {archived}")
    print(f"  Grand Total:  {new_total + unassigned + archived}")

    conn.close()
    print("\n[OK] DONE")

if __name__ == '__main__':
    run()
