"""
Part C — Full per-user reconciliation verification
Confirms: active + archived = total from source
"""
import urllib.request, json, sqlite3

API = "http://127.0.0.1:8000/api/v1"

def login(email, password="<set-password>"):
    data = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(f"{API}/auth/login", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]

def get(token, path):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

import time
time.sleep(3)  # Let backend start

print("=" * 70)
print("PART C — PER-USER RECONCILIATION REPORT")
print("=" * 70)

# Source truth (from CRM.xlsx + Gulf Leads analysis)
SOURCE = {
    "Saleh":  {"crm": 334,  "gulf": 1019},
    "Amin":   {"crm": 576,  "gulf": 1307},
    "Hasan":  {"crm": 548,  "gulf": 1174},
    "Ghaida": {"crm": 337,  "gulf": 337},
}

reps = [
    ("saleh@alphapromena.com",  "<set-password>", "Saleh"),
    ("amin@alphapromena.com",   "<set-password>", "Amin"),
    ("hasan@alphapromena.com",  "<set-password>", "Hasan"),
    ("ghaida@alphapromena.com", "<set-password>", "Ghaida"),
]

print(f"\n{'Rep':<10} {'Active(CRM)':<14} {'Archived(Gulf)':<16} {'Total':<10} {'Source Total':<14} {'Match'}")
print("-" * 80)

all_ok = True
for email, pwd, name in reps:
    try:
        token = login(email, pwd)
        
        # Active contacts
        resp_active = get(token, "/contacts?page=1&per_page=1&sort_by=sheet_order")
        active = resp_active.get("meta", {}).get("total", "?")
        
        # Archived contacts  
        resp_arch = get(token, "/contacts?page=1&per_page=1&status=ARCHIVED&include_archived=true")
        archived = resp_arch.get("meta", {}).get("total", "?")

        total = (active if isinstance(active, int) else 0) + (archived if isinstance(archived, int) else 0)
        source_total = SOURCE[name]["crm"] + SOURCE[name]["gulf"]
        exp_active = SOURCE[name]["crm"]
        exp_arch = SOURCE[name]["gulf"]

        active_ok = active == exp_active
        arch_ok = archived == exp_arch
        overall_ok = active_ok and arch_ok
        
        if not overall_ok:
            all_ok = False

        match_str = "OK" if overall_ok else f"MISMATCH(active={exp_active},arch={exp_arch})"
        print(f"{name:<10} {str(active):<14} {str(archived):<16} {str(total):<10} {str(source_total):<14} {match_str}")

    except Exception as e:
        print(f"{name:<10} ERROR: {e}")
        all_ok = False

print()

# Confirm infinite scroll is working: Amin has 576 records > 100 per page 
print("\n--- INFINITE SCROLL VERIFICATION ---")
print("(Confirming API can page beyond 100 for reps with 300+ contacts)")
try:
    token = login("amin@alphapromena.com")
    # Page 2 should have contacts
    resp_p2 = get(token, "/contacts?page=2&per_page=100&sort_by=sheet_order&sort_dir=asc")
    p2_items = len(resp_p2.get("data", []))
    p2_total = resp_p2.get("meta", {}).get("total", 0)
    p2_total_pages = resp_p2.get("meta", {}).get("total_pages", 0)
    print(f"  Amin page 2: {p2_items} contacts returned (total={p2_total}, total_pages={p2_total_pages})")
    
    # Page 6 (Amin 576/100 = 5.76 pages, page 6 should be partial or empty)
    resp_p6 = get(token, "/contacts?page=6&per_page=100&sort_by=sheet_order&sort_dir=asc")
    p6_items = len(resp_p6.get("data", []))
    print(f"  Amin page 6: {p6_items} contacts returned (last partial page)")
    print(f"  -> Scrolling through all {p2_total} Amin contacts requires {p2_total_pages} pages of 100")
    print(f"  -> Infinite scroll will auto-fetch pages 2-{p2_total_pages} as user scrolls")
except Exception as e:
    print(f"  ERROR: {e}")

# Archive outcome distribution via direct DB
print("\n--- ARCHIVE OUTCOME CLASSIFICATION ---")
conn = sqlite3.connect('c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\crm.db')
c = conn.cursor()
c.execute("""
    SELECT final_outcome, COUNT(*) as cnt
    FROM contacts
    WHERE status = 'ARCHIVED' AND deleted_at IS NULL
    GROUP BY final_outcome
    ORDER BY cnt DESC
""")
terminal_outcomes = {'Wrong Number', "Voice Mail / Don't Call Again", 'HQ / Switchboard', 
                      'Not Interested', 'No Answer (Max Attempts)'}
terminal_total = 0
non_terminal_total = 0
null_total = 0

for row in c.fetchall():
    fo = row[0]
    cnt = row[1]
    if fo is None:
        null_total += cnt
        category = "(no outcome)"
    elif fo in terminal_outcomes:
        terminal_total += cnt
        category = "[TERMINAL]"
    else:
        non_terminal_total += cnt
        category = "[active outcome]"
    print(f"  {category:<18} {fo or 'NULL':<35} {cnt}")

print(f"\n  Terminal outcomes (5 categories): {terminal_total}")
print(f"  Active outcomes in archive:        {non_terminal_total}")
print(f"  No outcome recorded:               {null_total}")
print(f"  Total archived:                    {terminal_total + non_terminal_total + null_total}")
conn.close()

print()
if all_ok:
    print("[OK] ALL COUNTS MATCH — RECONCILIATION PASSED")
else:
    print("[WARN] Some counts need review")
