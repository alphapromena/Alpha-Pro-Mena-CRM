"""
FULL PRODUCTION REIMPORT SCRIPT
================================
This script:
1. Identifies and removes ALL fake/generated/test data from the database
2. Verifies the CRM.xlsx active contacts are correct
3. Wipes all ARCHIVED records (they contain fake data mixed in)
4. Reimports COMPLETE Gulf Leads dataset into ARCHIVED status with real data only
5. Reports exact counts before and after

Run from: f:\\New folder\\backend
"""
import sqlite3
import openpyxl
import uuid
import re
from datetime import datetime, timezone
from collections import defaultdict

DB_PATH = 'f:\\New folder\\backend\\crm.db'
CRM_PATH = 'f:\\New folder\\CRM.xlsx'
GULF_PATH = 'f:\\New folder\\Gulf Leads .xlsx'

# User mapping: CRM/Gulf name -> DB user id
# Will be populated dynamically
USER_MAP = {}

def normalize_company_name(name):
    """Normalize company name for deduplication."""
    if not name:
        return ""
    s = str(name).strip().lower()
    s = re.sub(r"[\-_.,/\\&()+]", " ", s)
    tokens = s.split()
    suffixes = {
        "ltd", "limited", "llc", "inc", "incorporated", "corp", "corporation",
        "co", "company", "group", "holding", "holdings", "saudi", "ksa", "uae",
        "dubai", "gulf", "international", "intl", "services", "solutions", "est"
    }
    filtered = [t for t in tokens if t not in suffixes]
    return " ".join(filtered) if filtered else " ".join(tokens)

def normalize_phone(phone):
    """Normalize phone for deduplication."""
    if not phone:
        return None
    p = re.sub(r"[^\d+]", "", str(phone).strip())
    return p if len(p) >= 7 else None

def normalize_email(email):
    """Normalize email."""
    if not email:
        return None
    e = str(email).strip().lower()
    return e if "@" in e else None

def load_crm_xlsx():
    """Load CRM.xlsx data. No headers - col 0=Name,1=Company,2=Position,3=Phone,4=Email,5=SalesPerson"""
    wb = openpyxl.load_workbook(CRM_PATH, read_only=True, data_only=True)
    ws = wb['Sheet1']
    
    records = []
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if all(v is None or str(v).strip() == '' for v in row):
            continue
        
        name = str(row[0]).strip() if row[0] is not None else None
        company = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
        position = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
        phone = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
        email = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
        sp = str(row[5]).strip() if len(row) > 5 and row[5] is not None else 'UNKNOWN'
        
        if not name and not phone and not company:
            continue
            
        records.append({
            'row_idx': row_idx,
            'name': name,
            'company': company,
            'position': position,
            'phone': phone,
            'email': email,
            'sales_person': sp,
        })
    wb.close()
    return records

def load_gulf_leads_xlsx():
    """Load Gulf Leads .xlsx - Leads sheet only.
    Row 1 = headers: col 0=Name, 1=Company, 2=Position, 3=Phone, 4=Email, 5=SalesPerson, 6=Attempt1, 7=Attempt2, 8=Attempt3
    """
    wb = openpyxl.load_workbook(GULF_PATH, read_only=True, data_only=True)
    ws = wb['Leads']
    
    records = []
    skip_header = True
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if skip_header:
            skip_header = False
            continue  # Skip header row
        
        if all(v is None or str(v).strip() == '' for v in row):
            continue
        
        name = str(row[0]).strip() if row[0] is not None else None
        company = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
        position = str(row[2]).strip() if len(row) > 2 and row[2] is not None else None
        phone = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
        email = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
        sp = str(row[5]).strip() if len(row) > 5 and row[5] is not None else 'UNKNOWN'
        attempt_1 = str(row[6]).strip() if len(row) > 6 and row[6] is not None else None
        attempt_2 = str(row[7]).strip() if len(row) > 7 and row[7] is not None else None
        attempt_3 = str(row[8]).strip() if len(row) > 8 and row[8] is not None else None
        notes = str(row[10]).strip() if len(row) > 10 and row[10] is not None else None
        
        if not name and not phone and not company:
            continue
        
        records.append({
            'row_idx': row_idx,
            'name': name,
            'company': company,
            'position': position,
            'phone': phone,
            'email': email,
            'sales_person': sp,
            'attempt_1': attempt_1,
            'attempt_2': attempt_2,
            'attempt_3': attempt_3,
            'notes': notes,
        })
    wb.close()
    return records

def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    print("=" * 70)
    print("PRODUCTION REIMPORT SCRIPT")
    print("=" * 70)

    # ================================================
    # STEP 1: Load users and build mapping
    # ================================================
    print("\n[1] Loading users...")
    c.execute("SELECT id, first_name, last_name, email, role FROM users WHERE deleted_at IS NULL")
    users = c.fetchall()
    for u in users:
        fname = (u['first_name'] or '').strip()
        lname = (u['last_name'] or '').strip()
        full = f"{fname} {lname}".strip()
        USER_MAP[fname.lower()] = u['id']
        USER_MAP[full.lower()] = u['id']
        print(f"  User: {fname} (id={u['id'][:8]}...)")
    
    # Manual mappings for source variations
    # CRM.xlsx uses 'Hassan' -> Hasan user
    USER_MAP['hassan'] = USER_MAP.get('hasan')
    USER_MAP['amin'] = USER_MAP.get('amin')
    USER_MAP['saleh'] = USER_MAP.get('saleh')
    USER_MAP['ghaida'] = USER_MAP.get('ghaida')
    USER_MAP['qusai'] = USER_MAP.get('qusai')
    
    print(f"  USER_MAP keys: {list(USER_MAP.keys())}")
    
    # ================================================
    # STEP 2: Analyze current DB state
    # ================================================
    print("\n[2] Current DB state:")
    
    c.execute("SELECT status, COUNT(*) FROM contacts GROUP BY status")
    for row in c.fetchall():
        print(f"  status={row[0]}: {row[1]}")
    
    c.execute("SELECT COUNT(*) FROM contacts WHERE (first_name || ' ' || COALESCE(last_name,'')) LIKE 'Contact_0%'")
    fake_contact0 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM contacts WHERE email LIKE '%@elmtest.sa'")
    fake_elmtest = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM contacts WHERE first_name LIKE 'IdempotentLead%'")
    fake_idempotent = c.fetchone()[0]
    
    print(f"\n  Fake Contact_0 records: {fake_contact0}")
    print(f"  Fake @elmtest.sa records: {fake_elmtest}")
    print(f"  Fake IdempotentLead records: {fake_idempotent}")
    
    # ================================================
    # STEP 3: Load source files and count
    # ================================================
    print("\n[3] Loading CRM.xlsx source data...")
    crm_records = load_crm_xlsx()
    crm_by_rep = defaultdict(list)
    for r in crm_records:
        crm_by_rep[r['sales_person'].lower()].append(r)
    
    print(f"  Total rows loaded: {len(crm_records)}")
    for rep, rows in sorted(crm_by_rep.items()):
        print(f"  '{rep}': {len(rows)}")
    
    print("\n[4] Loading Gulf Leads .xlsx source data (Leads sheet only)...")
    gulf_records = load_gulf_leads_xlsx()
    gulf_by_rep = defaultdict(list)
    for r in gulf_records:
        gulf_by_rep[r['sales_person'].lower()].append(r)
    
    print(f"  Total rows loaded: {len(gulf_records)}")
    for rep, rows in sorted(gulf_by_rep.items()):
        print(f"  '{rep}': {len(rows)}")
    
    # ================================================
    # STEP 4: Verify active CRM contacts match source
    # ================================================
    print("\n[5] Verifying active CRM contacts vs source...")
    
    rep_checks = [
        ('saleh', 'saleh'),
        ('amin', 'amin'),
        ('hassan', 'hasan'),  # CRM uses 'Hassan', DB user is 'Hasan'
        ('ghaida', 'ghaida'),
    ]
    
    for crm_rep_key, db_user_key in rep_checks:
        source_count = len(crm_by_rep.get(crm_rep_key, []))
        user_id = USER_MAP.get(db_user_key)
        if user_id:
            c.execute(
                "SELECT COUNT(*) FROM contacts WHERE owner_id=? AND status!='ARCHIVED' AND status!='UNASSIGNED' AND deleted_at IS NULL",
                (user_id,)
            )
            db_count = c.fetchone()[0]
        else:
            db_count = 0
        
        match = "[MATCH]" if source_count == db_count else f"[MISMATCH] source={source_count} db={db_count}"
        print(f"  {crm_rep_key}: {match}")
    
    # ================================================
    # STEP 5: WIPE ALL ARCHIVED records (they have fake data)
    # ================================================
    print("\n[6] Wiping ALL archived contacts to reimport from real Gulf Leads data...")
    
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='ARCHIVED'")
    archived_before = c.fetchone()[0]
    print(f"  Archived contacts before wipe: {archived_before}")
    
    # Get IDs of archived contacts
    c.execute("SELECT id FROM contacts WHERE status='ARCHIVED'")
    archived_ids = [r[0] for r in c.fetchall()]
    
    # Delete related records for archived contacts
    if archived_ids:
        # Use chunks for large deletions
        chunk_size = 500
        chunks = [archived_ids[i:i+chunk_size] for i in range(0, len(archived_ids), chunk_size)]
        
        for chunk in chunks:
            placeholders = ','.join('?' * len(chunk))
            c.execute(f"DELETE FROM calls WHERE contact_id IN ({placeholders})", chunk)
            c.execute(f"DELETE FROM contact_notes WHERE contact_id IN ({placeholders})", chunk)
            c.execute(f"DELETE FROM tasks WHERE contact_id IN ({placeholders})", chunk)
            c.execute(f"DELETE FROM recalls WHERE contact_id IN ({placeholders})", chunk)
            c.execute(f"DELETE FROM no_answer_queue WHERE contact_id IN ({placeholders})", chunk)
            c.execute(f"DELETE FROM follow_ups WHERE contact_id IN ({placeholders})", chunk)
            c.execute(f"DELETE FROM demos WHERE contact_id IN ({placeholders})", chunk)
            c.execute(f"DELETE FROM campaign_contacts WHERE contact_id IN ({placeholders})", chunk)
        
        c.execute("DELETE FROM contacts WHERE status='ARCHIVED'")
        deleted_archived = c.rowcount
        print(f"  Deleted {deleted_archived} archived contacts and their linked records")
    
    # Also delete fake/test active contacts (Contact_0, IdempotentLead, etc.)
    c.execute("DELETE FROM contacts WHERE first_name LIKE 'Contact_0%' AND status != 'ARCHIVED'")
    fake_deleted = c.rowcount
    c.execute("DELETE FROM contacts WHERE first_name LIKE 'IdempotentLead%'")
    idempotent_deleted = c.rowcount
    c.execute("DELETE FROM contacts WHERE email LIKE '%@elmtest.sa'")
    elmtest_deleted = c.rowcount
    c.execute("DELETE FROM contacts WHERE email LIKE '%@testcompany.com'")
    testcompany_deleted = c.rowcount
    
    if fake_deleted + idempotent_deleted + elmtest_deleted + testcompany_deleted > 0:
        print(f"  Also deleted: {fake_deleted} Contact_0, {idempotent_deleted} Idempotent, {elmtest_deleted} elmtest, {testcompany_deleted} testcompany active fakes")
    
    conn.commit()
    
    # ================================================
    # STEP 6: Load companies for deduplication
    # ================================================
    print("\n[7] Loading existing companies...")
    c.execute("SELECT id, name FROM companies WHERE deleted_at IS NULL")
    company_rows = c.fetchall()
    company_cache = {}  # normalized_name -> id
    for row in company_rows:
        norm = normalize_company_name(row['name'])
        if norm:
            company_cache[norm] = row['id']
    print(f"  {len(company_cache)} companies in cache")
    
    def get_or_create_company(company_name):
        if not company_name:
            return None
        norm = normalize_company_name(company_name)
        if norm in company_cache:
            return company_cache[norm]
        # Create new company
        new_id = str(uuid.uuid4())
        c.execute(
            "INSERT INTO companies (id, name, status, created_at, updated_at) VALUES (?, ?, 'ACTIVE', ?, ?)",
            (new_id, company_name.strip(), now, now)
        )
        company_cache[norm] = new_id
        return new_id
    
    # ================================================
    # STEP 7: Import COMPLETE Gulf Leads as ARCHIVED
    # ================================================
    print("\n[8] Importing Gulf Leads (Leads sheet) as ARCHIVED contacts...")
    
    # Map Gulf rep names to DB user ids
    gulf_rep_to_user = {
        'saleh': USER_MAP.get('saleh'),
        'amin': USER_MAP.get('amin'),
        'hassan': USER_MAP.get('hasan'),  # Gulf uses 'Hassan'
        'ghaida': USER_MAP.get('ghaida'),
        'qusai': USER_MAP.get('qusai'),
        'maria': None,   # no DB user
        'raneem': None,  # no DB user
    }
    
    gulf_imported = 0
    gulf_skipped_norep = 0
    gulf_by_rep_imported = defaultdict(int)
    
    for record in gulf_records:
        sp_key = record['sales_person'].lower()
        owner_id = gulf_rep_to_user.get(sp_key)
        
        if owner_id is None and sp_key not in gulf_rep_to_user:
            # Unknown rep - try to find by name
            owner_id = USER_MAP.get(sp_key)
        
        # Parse name
        name_str = record['name'] or ''
        parts = name_str.strip().split(' ', 1)
        first_name = parts[0] if parts else 'Unknown'
        last_name = parts[1] if len(parts) > 1 else None
        
        # Skip rows with no useful data
        if not first_name or first_name.lower() in ('no answer', 'none', 'unknown', ''):
            gulf_skipped_norep += 1
            continue
        
        company_id = get_or_create_company(record['company'])
        phone = normalize_phone(record['phone'])
        email = normalize_email(record['email'])
        
        contact_id = str(uuid.uuid4())
        sheet_order = record['row_idx']
        
        c.execute("""
            INSERT INTO contacts (
                id, first_name, last_name, company_id, position,
                phone, normalized_phone, email, normalized_email,
                owner_id, status, priority, is_dnc, attempt_count,
                source, source_sheet,
                attempt_1, attempt_2, attempt_3,
                notes, sheet_order,
                created_at, updated_at, archived_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, 'ARCHIVED', 'MEDIUM', 0, 0,
                'IMPORT', 'Leads',
                ?, ?, ?,
                ?, ?,
                ?, ?, ?
            )
        """, (
            contact_id,
            first_name, last_name,
            company_id, record['position'],
            record['phone'], phone,
            record['email'], email,
            owner_id,
            record['attempt_1'], record['attempt_2'], record['attempt_3'],
            record['notes'], sheet_order,
            now, now, now
        ))
        
        gulf_imported += 1
        gulf_by_rep_imported[sp_key] += 1
    
    conn.commit()
    print(f"  Total Gulf Leads imported as ARCHIVED: {gulf_imported}")
    print(f"  Skipped (no usable name): {gulf_skipped_norep}")
    print(f"  By rep:")
    for rep, count in sorted(gulf_by_rep_imported.items()):
        print(f"    '{rep}': {count}")
    
    # ================================================
    # STEP 8: Verify CRM active contacts - fix missing Saleh record
    # ================================================
    print("\n[9] Verifying CRM.xlsx active contacts...")
    
    saleh_id = USER_MAP.get('saleh')
    if saleh_id:
        c.execute(
            "SELECT COUNT(*) FROM contacts WHERE owner_id=? AND status NOT IN ('ARCHIVED', 'UNASSIGNED') AND deleted_at IS NULL",
            (saleh_id,)
        )
        saleh_db_count = c.fetchone()[0]
        saleh_source_count = len(crm_by_rep.get('saleh', []))
        
        print(f"  Saleh in DB: {saleh_db_count} | Source: {saleh_source_count}")
        
        if saleh_db_count < saleh_source_count:
            # Find which records are missing by import_key or phone
            print(f"  Saleh is MISSING {saleh_source_count - saleh_db_count} record(s). Importing missing...")
            
            # Get existing phone numbers for Saleh active contacts
            c.execute(
                "SELECT normalized_phone, first_name, last_name FROM contacts WHERE owner_id=? AND status NOT IN ('ARCHIVED', 'UNASSIGNED') AND deleted_at IS NULL",
                (saleh_id,)
            )
            existing_saleh = {(r[0], (r[1] or '').lower() + ' ' + (r[2] or '').lower()): True for r in c.fetchall()}
            
            for record in crm_by_rep.get('saleh', []):
                norm_ph = normalize_phone(record['phone'])
                name_str = record['name'] or ''
                parts = name_str.strip().split(' ', 1)
                first_name = parts[0] if parts else ''
                last_name = parts[1] if len(parts) > 1 else None
                name_key = ((first_name or '').lower() + ' ' + (last_name or '').lower())
                
                if (norm_ph, name_key.strip()) not in existing_saleh:
                    company_id = get_or_create_company(record['company'])
                    contact_id = str(uuid.uuid4())
                    phone = normalize_phone(record['phone'])
                    email = normalize_email(record['email'])
                    
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
                            ?, 'NEW', 'MEDIUM', 0, 0,
                            'IMPORT', 'Sheet1', ?,
                            ?, ?
                        )
                    """, (
                        contact_id,
                        first_name, last_name,
                        company_id, record['position'],
                        record['phone'], phone,
                        record['email'], email,
                        saleh_id,
                        record['row_idx'],
                        now, now
                    ))
                    print(f"  Inserted missing: {first_name} {last_name or ''} | {record['phone']}")
            
            conn.commit()
    
    # ================================================
    # STEP 9: FINAL VERIFICATION
    # ================================================
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION REPORT")
    print("=" * 70)
    
    print("\n--- CRM.xlsx SOURCE COUNTS ---")
    print(f"  Total: {len(crm_records)}")
    for sp_key in ['saleh', 'amin', 'hassan', 'ghaida']:
        print(f"  {sp_key.capitalize()}: {len(crm_by_rep.get(sp_key, []))}")
    print(f"  Unassigned (UNKNOWN): {len(crm_by_rep.get('unknown', []))}")
    
    print("\n--- IMPORTED ACTIVE CONTACTS (DB) ---")
    total_active_final = 0
    for crm_key, db_key in [('saleh', 'saleh'), ('amin', 'amin'), ('hassan', 'hasan'), ('ghaida', 'ghaida')]:
        uid = USER_MAP.get(db_key)
        if uid:
            c.execute(
                "SELECT COUNT(*) FROM contacts WHERE owner_id=? AND status NOT IN ('ARCHIVED', 'UNASSIGNED') AND deleted_at IS NULL",
                (uid,)
            )
            count = c.fetchone()[0]
            source = len(crm_by_rep.get(crm_key, []))
            match = "OK" if count == source else f"MISMATCH (source={source})"
            print(f"  {crm_key.capitalize()}: {count} {match}")
            total_active_final += count
    
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='UNASSIGNED' AND deleted_at IS NULL")
    unassigned_count = c.fetchone()[0]
    print(f"  Unassigned: {unassigned_count}")
    total_active_final += unassigned_count
    print(f"  TOTAL ACTIVE: {total_active_final}")
    
    print("\n--- Gulf Leads SOURCE COUNTS (Leads sheet only) ---")
    print(f"  Total: {len(gulf_records)}")
    for sp_key in ['saleh', 'amin', 'hassan', 'ghaida']:
        print(f"  {sp_key.capitalize()}: {len(gulf_by_rep.get(sp_key, []))}")
    
    print("\n--- ARCHIVED CONTACTS (DB) ---")
    total_archived_final = 0
    for gulf_key, db_key in [('saleh', 'saleh'), ('amin', 'amin'), ('hassan', 'hasan'), ('ghaida', 'ghaida')]:
        uid = USER_MAP.get(db_key)
        if uid:
            c.execute(
                "SELECT COUNT(*) FROM contacts WHERE owner_id=? AND status='ARCHIVED' AND deleted_at IS NULL",
                (uid,)
            )
            count = c.fetchone()[0]
            source = len(gulf_by_rep.get(gulf_key, []))
            match = "OK" if count == source else f"MISMATCH (source={source})"
            print(f"  {gulf_key.capitalize()}: {count} {match}")
            total_archived_final += count
    
    # Others (maria, raneem, etc.) - archived with no owner
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='ARCHIVED' AND owner_id IS NULL AND deleted_at IS NULL")
    no_owner_archived = c.fetchone()[0]
    print(f"  No owner (UNKNOWN/Maria/Raneem): {no_owner_archived}")
    
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='ARCHIVED' AND deleted_at IS NULL")
    total_archived_final = c.fetchone()[0]
    print(f"  TOTAL ARCHIVED: {total_archived_final}")
    
    print("\n--- FAKE DATA CHECK ---")
    c.execute("SELECT COUNT(*) FROM contacts WHERE first_name LIKE 'Contact_0%'")
    print(f"  Fake Contact_0 records remaining: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM contacts WHERE email LIKE '%@elmtest.sa'")
    print(f"  Fake @elmtest.sa records remaining: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM contacts WHERE first_name LIKE 'IdempotentLead%'")
    print(f"  Fake IdempotentLead records remaining: {c.fetchone()[0]}")
    
    print("\n--- NO ANSWER QUEUE ---")
    c.execute("SELECT COUNT(*) FROM no_answer_queue")
    print(f"  No Answer Queue records: {c.fetchone()[0]}")
    
    print("\n--- EMAIL & WHATSAPP (Activity scope) ---")
    c.execute("SELECT COUNT(*) FROM email_activities")
    ea = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM whatsapp_activities")
    wa = c.fetchone()[0]
    print(f"  Email activities: {ea}")
    print(f"  WhatsApp activities: {wa}")
    
    print()
    print("\n[OK] PRODUCTION REIMPORT COMPLETE")
    
    conn.close()

if __name__ == '__main__':
    run()
