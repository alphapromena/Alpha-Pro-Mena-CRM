"""
ATTEMPT HISTORY AUDIT
======================
Systematic comparison of:
  1. What CRM.xlsx records (attempt columns 6, 7, 8) for each contact
  2. What the DB has (attempt_1, attempt_2, attempt_3 + calls table)
"""
import sqlite3
import openpyxl
from collections import defaultdict

DB_PATH = 'f:\\New folder\\backend\\crm.db'
CRM_PATH = 'f:\\New folder\\CRM.xlsx'

def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("=" * 70)
    print("ATTEMPT HISTORY AUDIT")
    print("=" * 70)

    # ── STEP 1: Check the 3 named stc Bank contacts ──────────────────────────
    print("\n--- NAMED stc Bank CONTACTS (Saleh) ---")
    names_to_check = ['Ayman Ali', 'Raghad Alhammad', 'Yousif Elamin']
    for name in names_to_check:
        parts = name.split(' ', 1)
        c.execute("""
            SELECT ct.first_name, ct.last_name, ct.phone, ct.attempt_1, ct.attempt_2, ct.attempt_3,
                   ct.attempt_count, ct.sheet_order
            FROM contacts ct
            WHERE ct.first_name=? AND ct.last_name=?
              AND ct.deleted_at IS NULL
        """, (parts[0], parts[1] if len(parts) > 1 else None))
        rows = c.fetchall()
        for r in rows:
            print(f"  {r['first_name']} {r['last_name']} | phone={r['phone']} | "
                  f"attempt_1={r['attempt_1']!r} | attempt_2={r['attempt_2']!r} | attempt_3={r['attempt_3']!r} | "
                  f"attempt_count={r['attempt_count']} | sheet_order={r['sheet_order']}")
        if not rows:
            print(f"  {name}: NOT FOUND in DB")

    # ── STEP 2: Load CRM.xlsx and check what it has for these rows ───────────
    print("\n--- CRM.xlsx RAW DATA for stc Bank contacts (Saleh) ---")
    wb = openpyxl.load_workbook(CRM_PATH, read_only=True, data_only=True)
    ws = wb['Sheet1']
    print("Row | Name | Company | Position | Phone | Email | Rep | Attempt1 | Attempt2 | Attempt3")
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if i < 118 or i > 135:
            continue
        if row[5] and 'saleh' in str(row[5]).lower():
            a1 = row[6] if len(row) > 6 else None
            a2 = row[7] if len(row) > 7 else None
            a3 = row[8] if len(row) > 8 else None
            print(f"  Row {i}: {row[0]} | Company/Pos={row[1]}/{row[2]} | Phone={row[3]} | "
                  f"A1={a1!r} | A2={a2!r} | A3={a3!r}")
    wb.close()

    # ── STEP 3: Broad audit — all contacts, count those with/without attempts ─
    print("\n--- BROAD AUDIT: Attempt data presence by rep ---")
    c.execute("""
        SELECT u.first_name as owner,
               COUNT(*) as total,
               SUM(CASE WHEN attempt_1 IS NOT NULL AND attempt_1 != '' THEN 1 ELSE 0 END) as has_a1,
               SUM(CASE WHEN attempt_2 IS NOT NULL AND attempt_2 != '' THEN 1 ELSE 0 END) as has_a2,
               SUM(CASE WHEN attempt_3 IS NOT NULL AND attempt_3 != '' THEN 1 ELSE 0 END) as has_a3,
               SUM(CASE WHEN attempt_1 IS NULL OR attempt_1 = '' THEN 1 ELSE 0 END) as missing_a1
        FROM contacts ct
        LEFT JOIN users u ON ct.owner_id = u.id
        WHERE ct.status = 'NEW'
          AND ct.deleted_at IS NULL
        GROUP BY ct.owner_id, u.first_name
        ORDER BY u.first_name
    """)
    print(f"  {'Owner':<12} {'Total':<8} {'Has A1':<10} {'Has A2':<10} {'Has A3':<10} {'Missing A1'}")
    print("  " + "-" * 60)
    for r in c.fetchall():
        print(f"  {r['owner'] or 'Unknown':<12} {r['total']:<8} {r['has_a1']:<10} {r['has_a2']:<10} {r['has_a3']:<10} {r['missing_a1']}")

    # ── STEP 4: Calls table — are there any call records for active contacts? ─
    print("\n--- CALLS TABLE: Active contacts with call records ---")
    c.execute("""
        SELECT COUNT(DISTINCT ct.id) as contacts_with_calls
        FROM contacts ct
        JOIN calls cl ON ct.id = cl.contact_id
        WHERE ct.status = 'NEW' AND ct.deleted_at IS NULL
    """)
    print(f"  Active contacts with entries in calls table: {c.fetchone()[0]}")

    # ── STEP 5: Check column counts in CRM.xlsx ──────────────────────────────
    print("\n--- CRM.xlsx: Column count range (do all rows have 9+ columns?) ---")
    wb = openpyxl.load_workbook(CRM_PATH, read_only=True, data_only=True)
    ws = wb['Sheet1']
    col_count_dist = defaultdict(int)
    for row in ws.iter_rows(values_only=True):
        if all(v is None for v in row):
            continue
        # Count non-None columns
        non_none = sum(1 for v in row if v is not None)
        col_count_dist[non_none] += 1
    wb.close()
    for ncols in sorted(col_count_dist.keys()):
        print(f"  Rows with {ncols} non-None cols: {col_count_dist[ncols]}")

    # ── STEP 6: Per-row CRM.xlsx attempt presence vs DB attempt presence ──────
    print("\n--- CRM.xlsx per-rep: rows WITH attempt data in cols 6/7/8 ---")
    wb = openpyxl.load_workbook(CRM_PATH, read_only=True, data_only=True)
    ws = wb['Sheet1']
    src_by_rep = defaultdict(lambda: {'total': 0, 'has_a1': 0, 'has_a2': 0, 'blank_a1': 0})
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if all(v is None for v in row):
            continue
        sp = str(row[5]).strip().lower() if len(row) > 5 and row[5] else 'unknown'
        a1 = row[6] if len(row) > 6 else None
        a2 = row[7] if len(row) > 7 else None
        src_by_rep[sp]['total'] += 1
        if a1 and str(a1).strip():
            src_by_rep[sp]['has_a1'] += 1
        else:
            src_by_rep[sp]['blank_a1'] += 1
        if a2 and str(a2).strip():
            src_by_rep[sp]['has_a2'] += 1
    wb.close()
    print(f"  {'Rep':<12} {'Total':<8} {'Has A1 (src)':<14} {'Blank A1 (src)'}")
    print("  " + "-" * 50)
    for rep in sorted(src_by_rep.keys()):
        d = src_by_rep[rep]
        print(f"  {rep:<12} {d['total']:<8} {d['has_a1']:<14} {d['blank_a1']}")

    conn.close()
    print("\n[OK] AUDIT COMPLETE")

if __name__ == '__main__':
    run()
