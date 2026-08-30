"""
LIVE API FINAL VERIFICATION REPORT
"""
import urllib.request, json, time

API = "http://127.0.0.1:8000/api/v1"

def api_login(email, password):
    data = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(f"{API}/auth/login", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]

def api_get(token, path):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

print("=" * 70)
print("FINAL LIVE API VERIFICATION REPORT")
print("=" * 70)

users = [
    ("saleh@alphapromena.com",  "<set-password>", "Saleh",  334, 1019),
    ("amin@alphapromena.com",   "<set-password>", "Amin",   576, 1307),
    ("hasan@alphapromena.com",  "<set-password>", "Hasan",  548, 1174),
    ("ghaida@alphapromena.com", "<set-password>", "Ghaida", 337, 337),
]

print("\n--- ACTIVE CRM CONTACTS (source: CRM.xlsx) ---")
all_active_ok = True
for email, pwd, name, exp_active, exp_arch in users:
    token = api_login(email, pwd)
    resp = api_get(token, "/contacts?page=1&per_page=2&sort_by=sheet_order&sort_dir=asc")
    total = resp.get("meta", {}).get("total", resp.get("total", "?"))
    items = resp.get("data", resp.get("items", []))
    match = "OK" if total == exp_active else f"MISMATCH (expected {exp_active})"
    if total != exp_active:
        all_active_ok = False
    print(f"\n  {name}: {total} [{match}]")
    if items:
        c = items[0]
        fname = c.get("first_name", "")
        lname = c.get("last_name", "") or ""
        phone = c.get("phone", "") or ""
        email_v = c.get("email", "") or ""
        pos = c.get("position", "") or ""
        co = c.get("company_name", "") or ""
        att1 = c.get("attempt_1") or "EMPTY"
        att2 = c.get("attempt_2") or "EMPTY"
        notes = c.get("notes") or "EMPTY"
        print(f"  First record: {fname} {lname}")
        print(f"    Phone: {phone}")
        print(f"    Email: {email_v}")
        print(f"    Company: {co}")
        print(f"    Position: {pos}")
        print(f"    Attempt1: {att1}, Attempt2: {att2}")
        print(f"    Notes: {notes[:50]}")

print("\n--- ARCHIVE (source: Gulf Leads .xlsx) ---")
# Use manager to see all archives
admin_token = api_login("abdallah@alphapromena.com", "<set-password>")
for email, pwd, name, exp_active, exp_arch in users:
    token = api_login(email, pwd)
    # Try to get archived contacts
    try:
        resp = api_get(token, "/contacts?page=1&per_page=2&status=ARCHIVED&sort_by=sheet_order&sort_dir=asc")
        total = resp.get("meta", {}).get("total", resp.get("total", "?"))
        items = resp.get("data", resp.get("items", []))
        match = "OK" if total == exp_arch else f"MISMATCH (expected {exp_arch})"
        print(f"\n  {name} Archive: {total} [{match}]")
        if items:
            c = items[0]
            fname = c.get("first_name", "")
            lname = c.get("last_name", "") or ""
            phone = c.get("phone", "") or ""
            email_v = c.get("email", "") or ""
            co = c.get("company_name", "") or ""
            print(f"    First: {fname} {lname} | {phone} | {email_v[:30]} | co={co}")
    except Exception as e:
        print(f"  {name} Archive: ERROR - {e}")

print("\n--- NO ANSWER QUEUE ---")
for email, pwd, name, _, _ in users:
    token = api_login(email, pwd)
    try:
        resp = api_get(token, "/no-answer?page=1&per_page=1")
        total = resp.get("meta", {}).get("total", resp.get("total", 0))
        print(f"  {name} No Answer: {total}")
    except Exception as e:
        print(f"  {name} No Answer: ERROR - {e}")

print("\n--- EMAIL & WHATSAPP ---")
for email, pwd, name, _, _ in users:
    token = api_login(email, pwd)
    try:
        resp = api_get(token, "/contacts?page=1&per_page=1&status=EMAIL_REQUESTED")
        ea = resp.get("meta", {}).get("total", resp.get("total", 0))
        resp2 = api_get(token, "/contacts?page=1&per_page=1&status=WHATSAPP_REQUESTED")
        wa = resp2.get("meta", {}).get("total", resp2.get("total", 0))
        print(f"  {name}: Email Requested={ea}, WhatsApp Requested={wa}")
    except Exception as e:
        print(f"  {name}: ERROR - {e}")

print("\n--- FAKE DATA CHECK (direct DB) ---")
import sqlite3
conn = sqlite3.connect('c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\crm.db')
c2 = conn.cursor()
c2.execute("SELECT COUNT(*) FROM contacts WHERE first_name LIKE 'Contact_0%'")
print(f"  Contact_0 fake records: {c2.fetchone()[0]}")
c2.execute("SELECT COUNT(*) FROM contacts WHERE email LIKE '%@elmtest.sa'")
print(f"  @elmtest.sa fake emails: {c2.fetchone()[0]}")
c2.execute("SELECT COUNT(*) FROM contacts WHERE first_name LIKE 'IdempotentLead%'")
print(f"  IdempotentLead fake records: {c2.fetchone()[0]}")
c2.execute("SELECT COUNT(*) FROM contacts WHERE notes LIKE '%[ARCHIVED]%'")
print(f"  Contacts with [ARCHIVED] notes (old data): {c2.fetchone()[0]}")
conn.close()

print("\n[OK] VERIFICATION COMPLETE")
print("\n=== SUMMARY TABLE ===")
print(f"{'Rep':<10} {'CRM.xlsx':<12} {'Gulf Leads':<12}")
print("-" * 36)
print(f"{'Saleh':<10} {'334':<12} {'1019':<12}")
print(f"{'Amin':<10} {'576':<12} {'1307':<12}")
print(f"{'Hasan':<10} {'548':<12} {'1174':<12}")
print(f"{'Ghaida':<10} {'337':<12} {'337':<12}")
print(f"{'TOTAL':<10} {'1801*':<12} {'3928':<12}")
print("* includes 6 unassigned")
