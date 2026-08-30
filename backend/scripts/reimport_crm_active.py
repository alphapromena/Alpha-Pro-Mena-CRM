"""
COMPLETE CRM ACTIVE CONTACTS REIMPORT
=======================================
Wipes ALL active CRM contacts and reimports them cleanly from CRM.xlsx
with correct column mapping:
  Col 0 = Name
  Col 1 = Company
  Col 2 = Position
  Col 3 = Phone
  Col 4 = Email
  Col 5 = Sales Person

All attempts start EMPTY. No fake notes. No historical data.
"""
import sqlite3
import openpyxl
import uuid
import re
from datetime import datetime, timezone
from collections import defaultdict

DB_PATH = 'c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\crm.db'
CRM_PATH = 'c:/Users/user/Alpha-Pro-Mena-CRM\\CRM.xlsx'

def normalize_phone(phone):
    if not phone:
        return None
    p = re.sub(r'[^\d+]', '', str(phone).strip())
    return p if len(p) >= 7 else None

def normalize_email(email):
    if not email:
        return None
    e = str(email).strip().lower()
    return e if '@' in e else None

def normalize_company_name(name):
    if not name:
        return ""
    s = str(name).strip().lower()
    s = re.sub(r'[\-_.,/\\&()+]', ' ', s)
    tokens = s.split()
    suffixes = {
        'ltd', 'limited', 'llc', 'inc', 'incorporated', 'corp', 'corporation',
        'co', 'company', 'group', 'holding', 'holdings', 'international', 'intl',
        'services', 'solutions', 'est'
    }
    filtered = [t for t in tokens if t not in suffixes]
    return ' '.join(filtered) if filtered else ' '.join(tokens)

def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print("CRM ACTIVE CONTACTS CLEAN REIMPORT")
    print("=" * 70)

    # ── Load users ──────────────────────────────────────────────────────────
    c.execute("SELECT id, first_name FROM users WHERE deleted_at IS NULL")
    user_map = {}
    for u in c.fetchall():
        fname = (u['first_name'] or '').strip().lower()
        user_map[fname] = u['id']
    user_map['hassan'] = user_map.get('hasan')  # CRM uses 'Hassan'
    print(f"\nUsers loaded: {list(user_map.keys())}")

    # ── Count before ────────────────────────────────────────────────────────
    c.execute("SELECT status, COUNT(*) FROM contacts GROUP BY status")
    print("\nDB state before:")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")

    # ── Load CRM.xlsx ────────────────────────────────────────────────────────
    print("\nLoading CRM.xlsx...")
    wb = openpyxl.load_workbook(CRM_PATH, read_only=True, data_only=True)
    ws = wb['Sheet1']

    crm_records = []
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if all(v is None or str(v).strip() == '' for v in row):
            continue
        name    = str(row[0]).strip() if row[0] is not None else None
        col1    = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
        col2    = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
        phone   = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
        email   = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
        sp      = str(row[5]).strip() if len(row) > 5 and row[5] is not None else 'UNKNOWN'
        if not name:
            continue
        
        # CRM.xlsx column layout inconsistency:
        # - Hassan / Amin / Ghaida / UNKNOWN: col1=Company, col2=Position
        # - Saleh: col1=Position, col2=Company (inverted)
        if sp.lower() == 'saleh':
            company  = col2   # col2 is Company for Saleh
            position = col1   # col1 is Position for Saleh
        else:
            company  = col1   # col1 is Company for others
            position = col2   # col2 is Position for others
        
        crm_records.append({
            'row_idx': row_idx, 'name': name, 'company': company,
            'position': position, 'phone': phone, 'email': email,
            'sales_person': sp,
        })
    wb.close()

    by_rep = defaultdict(list)
    for r in crm_records:
        by_rep[r['sales_person'].lower()].append(r)

    print(f"Source rows loaded: {len(crm_records)}")
    for rep, rows in sorted(by_rep.items()):
        print(f"  '{rep}': {len(rows)}")

    # ── Delete all active + unassigned contacts ──────────────────────────────
    print("\nDeleting all active CRM contacts...")

    c.execute("SELECT id FROM contacts WHERE status NOT IN ('ARCHIVED') AND deleted_at IS NULL")
    active_ids = [r[0] for r in c.fetchall()]
    print(f"  Active/unassigned contacts to delete: {len(active_ids)}")

    if active_ids:
        chunk_size = 500
        for i in range(0, len(active_ids), chunk_size):
            chunk = active_ids[i:i+chunk_size]
            ph = ','.join('?' * len(chunk))
            c.execute(f"DELETE FROM calls WHERE contact_id IN ({ph})", chunk)
            c.execute(f"DELETE FROM contact_notes WHERE contact_id IN ({ph})", chunk)
            c.execute(f"DELETE FROM tasks WHERE contact_id IN ({ph})", chunk)
            c.execute(f"DELETE FROM recalls WHERE contact_id IN ({ph})", chunk)
            c.execute(f"DELETE FROM no_answer_queue WHERE contact_id IN ({ph})", chunk)
            c.execute(f"DELETE FROM follow_ups WHERE contact_id IN ({ph})", chunk)
            c.execute(f"DELETE FROM demos WHERE contact_id IN ({ph})", chunk)
            c.execute(f"DELETE FROM campaign_contacts WHERE contact_id IN ({ph})", chunk)
        c.execute("DELETE FROM contacts WHERE status NOT IN ('ARCHIVED') AND deleted_at IS NULL")
        print(f"  Deleted {c.rowcount} active contacts and linked records")

    conn.commit()

    # ── Load companies for deduplication ────────────────────────────────────
    c.execute("SELECT id, name FROM companies WHERE deleted_at IS NULL")
    company_cache = {}
    for row in c.fetchall():
        norm = normalize_company_name(row['name'])
        if norm:
            company_cache[norm] = row['id']
    print(f"\nCompanies in cache: {len(company_cache)}")

    def get_or_create_company(company_name):
        if not company_name:
            return None
        norm = normalize_company_name(company_name)
        if norm in company_cache:
            return company_cache[norm]
        new_id = str(uuid.uuid4())
        c.execute(
            "INSERT INTO companies (id, name, status, created_at, updated_at) VALUES (?, ?, 'ACTIVE', ?, ?)",
            (new_id, company_name.strip(), now, now)
        )
        company_cache[norm] = new_id
        return new_id

    # ── Import all CRM records ───────────────────────────────────────────────
    print("\nImporting CRM.xlsx contacts...")
    imported = 0
    skipped = 0
    by_rep_imported = defaultdict(int)

    for record in crm_records:
        sp_key = record['sales_person'].lower()
        owner_id = user_map.get(sp_key)  # None = UNASSIGNED
        status = 'UNASSIGNED' if owner_id is None else 'NEW'

        # Parse name
        parts = record['name'].strip().split(' ', 1)
        first_name = parts[0]
        last_name  = parts[1] if len(parts) > 1 else None

        if not first_name:
            skipped += 1
            continue

        company_id = get_or_create_company(record['company'])
        phone      = normalize_phone(record['phone'])
        email      = normalize_email(record['email'])
        contact_id = str(uuid.uuid4())

        c.execute("""
            INSERT INTO contacts (
                id, first_name, last_name, company_id, position,
                phone, normalized_phone, email, normalized_email,
                owner_id, status, priority, is_dnc, attempt_count,
                source, source_sheet, sheet_order,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, 'MEDIUM', 0, 0,
                'CRM.xlsx', 'Sheet1', ?,
                ?, ?
            )
        """, (
            contact_id,
            first_name, last_name,
            company_id, record['position'],
            record['phone'], phone,
            record['email'], email,
            owner_id, status,
            record['row_idx'],
            now, now
        ))

        imported += 1
        by_rep_imported[sp_key] += 1

    conn.commit()
    print(f"  Imported: {imported}")
    print(f"  Skipped (no name): {skipped}")
    for rep, count in sorted(by_rep_imported.items()):
        print(f"    '{rep}': {count}")

    # ── Final verification ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION")
    print("=" * 70)

    print("\nCRM.xlsx SOURCE vs DB:")
    rep_checks = [
        ('saleh', 'saleh', 334),
        ('amin', 'amin', 576),
        ('hassan', 'hasan', 548),
        ('ghaida', 'ghaida', 337),
        ('unknown', None, 6),
    ]
    for crm_key, db_key, expected in rep_checks:
        source_count = len(by_rep.get(crm_key, []))
        if db_key:
            uid = user_map.get(db_key)
            c.execute(
                "SELECT COUNT(*) FROM contacts WHERE owner_id=? AND status='NEW' AND deleted_at IS NULL",
                (uid,)
            )
        else:
            c.execute(
                "SELECT COUNT(*) FROM contacts WHERE status='UNASSIGNED' AND deleted_at IS NULL"
            )
        db_count = c.fetchone()[0]
        match = "OK" if source_count == db_count else f"MISMATCH (source={source_count} db={db_count})"
        print(f"  {crm_key.capitalize()}: source={source_count} db={db_count} [{match}]")

    # Verify archived contacts untouched
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='ARCHIVED'")
    archived_count = c.fetchone()[0]
    print(f"\nArchived contacts (Gulf Leads): {archived_count} (should be 3928)")

    # Verify first Saleh record is correct
    uid = user_map.get('saleh')
    c.execute(
        "SELECT first_name, last_name, phone, email, position, company_id FROM contacts WHERE owner_id=? AND status='NEW' ORDER BY sheet_order ASC LIMIT 3",
        (uid,)
    )
    print("\nFirst 3 Saleh CRM contacts (by sheet_order):")
    for row in c.fetchall():
        co = None
        if row['company_id']:
            c2 = conn.cursor()
            c2.execute("SELECT name FROM companies WHERE id=?", (row['company_id'],))
            res = c2.fetchone()
            co = res['name'] if res else None
        print(f"  {row['first_name']} {row['last_name'] or ''} | phone={row['phone']} | email={row['email']} | position={row['position']} | company={co}")

    print("\n[OK] REIMPORT COMPLETE")
    conn.close()

if __name__ == '__main__':
    run()
