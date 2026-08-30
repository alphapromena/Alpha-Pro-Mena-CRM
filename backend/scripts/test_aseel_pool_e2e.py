"""
ASEEL POOL WORKFLOW — END-TO-END LIVE TEST
============================================
1. Login as Aseel (data ops)
2. Check unassigned pool has leads
3. Distribute 3 leads to Saleh's personal pool
4. Login as Saleh — confirm leads are in his pool (PENDING_CLAIM), NOT in active contacts
5. Saleh claims 2 of the leads individually
6. Saleh bulk-claims the 3rd
7. Verify all 3 now appear in active contacts (NEW status), appended at end
8. Confirm they no longer appear in the pool
"""
import urllib.request, json, time, sqlite3

API = "http://127.0.0.1:8000/api/v1"

def login(email, password):
    data = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(f"{API}/auth/login", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read())
        return resp["access_token"]

def get(token, path, params=None):
    url = f"{API}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def post(token, path, body=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(f"{API}{path}", data=data,
                                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def step(n, msg):
    print(f"\n{'='*60}")
    print(f"STEP {n}: {msg}")
    print('='*60)

print("=" * 70)
print("ASEEL POOL WORKFLOW — LIVE END-TO-END TEST")
print("=" * 70)

# Step 1: Login as Aseel
step(1, "Login as Aseel")
try:
    aseel_token = login("aseel@alphapromena.com", "<set-password>")
    me = get(aseel_token, "/auth/me")
    print(f"  Logged in as: {me.get('first_name')} {me.get('last_name')} — role={me.get('role')}")
except Exception as e:
    print(f"  ERROR: {e}")
    exit(1)

# Step 2: Check unassigned pool
step(2, "Check unassigned lead pool (Aseel view)")
try:
    pool_resp = get(aseel_token, "/admin/leads/unassigned", {"per_page": 5})
    pool_total = pool_resp.get("meta", {}).get("total", 0)
    pool_leads = pool_resp.get("data", [])
    print(f"  Unassigned pool total: {pool_total}")
    for l in pool_leads[:3]:
        print(f"    - {l.get('first_name')} {l.get('last_name')} | status={l.get('status')}")
except Exception as e:
    print(f"  ERROR accessing /admin/leads/unassigned: {e}")
    pool_leads = []
    pool_total = 0

# Step 3: Get Saleh's user ID via distribution-status (accessible by DATA_OPS)
step(3, "Get Saleh's user ID via /admin/distribution-status")
try:
    status_resp = get(aseel_token, "/admin/distribution-status")
    # Response: {"data": {"summary": {...}, "sales_users": [...], "recent_assignments": [...]}}
    data_block = status_resp.get("data", status_resp)
    reps = data_block.get("sales_users", [])
    print(f"  Sales users returned: {len(reps)}")
    saleh = next((u for u in reps if u.get("first_name", "").lower() == "saleh"), None)
    if saleh:
        saleh_id = saleh["user_id"]
        print(f"  Saleh ID: {saleh_id}")
        print(f"  Saleh waiting_in_pool: {saleh.get('waiting_count', 0)}")
    else:
        print(f"  Reps found: {[r.get('first_name') for r in reps]}")
        # Fallback: get Saleh directly from DB
        import sqlite3
        conn2 = sqlite3.connect("c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\crm.db")
        c2 = conn2.cursor()
        c2.execute("SELECT id FROM users WHERE first_name='Saleh' AND deleted_at IS NULL LIMIT 1")
        row = c2.fetchone()
        conn2.close()
        saleh_id = row[0] if row else None
        print(f"  Fallback from DB: Saleh ID = {saleh_id}")
except Exception as e:
    print(f"  ERROR: {e}")
    import sqlite3
    conn2 = sqlite3.connect("c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\crm.db")
    c2 = conn2.cursor()
    c2.execute("SELECT id FROM users WHERE first_name='Saleh' AND deleted_at IS NULL LIMIT 1")
    row = c2.fetchone()
    conn2.close()
    saleh_id = row[0] if row else None
    print(f"  Fallback from DB: Saleh ID = {saleh_id}")

# Step 4: Distribute 3 leads to Saleh's personal pool
step(4, "Distribute 3 leads to Saleh's personal pool via MANUAL strategy")
if saleh_id and pool_total > 0:
    try:
        dist_resp = post(aseel_token, "/admin/leads/distribute", {
            "strategy": "MANUAL",
            "target_user_id": saleh_id,
            "count": 3
        })
        assigned = dist_resp.get("assigned_count", 0)
        msg = dist_resp.get("message", "")
        print(f"  Distributed: {assigned} leads")
        print(f"  Message: {msg}")
    except Exception as e:
        print(f"  ERROR distributing: {e}")
        assigned = 0
else:
    print(f"  SKIPPING — no unassigned leads in pool (total={pool_total}) or no saleh_id")
    assigned = 0

# Step 5: Login as Saleh, check personal pool
step(5, "Login as Saleh — verify leads in personal pool (PENDING_CLAIM)")
time.sleep(1)
try:
    saleh_token = login("saleh@alphapromena.com", "<set-password>")
    pool_check = get(saleh_token, "/contacts", {"pending_claim_only": "true", "per_page": 20})
    pool_items = pool_check.get("data", [])
    pool_count = pool_check.get("meta", {}).get("total", len(pool_items))
    print(f"  Saleh's personal pool (PENDING_CLAIM): {pool_count} leads")
    for item in pool_items[:5]:
        print(f"    - {item.get('first_name')} {item.get('last_name')} | status={item.get('status')} | id={item['id'][:8]}...")
except Exception as e:
    print(f"  ERROR: {e}")
    pool_items = []
    pool_count = 0

# Step 6: Check these leads are NOT in active contacts
step(6, "Confirm PENDING_CLAIM leads are NOT in active contacts list")
try:
    active_resp = get(saleh_token, "/contacts", {"per_page": 1})
    active_total_before = active_resp.get("meta", {}).get("total", 0)
    print(f"  Saleh active contacts (before claim): {active_total_before}")
    # Verify pool items not in active list
    if pool_items:
        pid = pool_items[0]["id"]
        # Pool item should have status PENDING_CLAIM
        pool_statuses = [item.get("status") for item in pool_items]
        print(f"  Pool item statuses: {set(pool_statuses)}")
        assert all(s == "PENDING_CLAIM" for s in pool_statuses), "FAIL: Pool items should all be PENDING_CLAIM"
        print(f"  OK: All {len(pool_items)} pool items have status=PENDING_CLAIM")
except Exception as e:
    print(f"  ERROR: {e}")

# Step 7: Claim leads individually (first 2)
step(7, "Saleh claims first 2 leads individually")
claimed_ids = []
if pool_items:
    for item in pool_items[:2]:
        try:
            claim_resp = post(saleh_token, f"/contacts/{item['id']}/claim")
            msg = claim_resp.get("message", "")
            new_status = claim_resp.get("data", {}).get("status", "?")
            print(f"  Claimed {item['first_name']} {item['last_name']}: status={new_status}")
            claimed_ids.append(item["id"])
        except Exception as e:
            print(f"  ERROR claiming {item['id']}: {e}")

# Step 8: Bulk claim the rest
step(8, "Saleh bulk-claims remaining pool leads")
if len(pool_items) > 2:
    remaining_ids = [item["id"] for item in pool_items[2:]]
    try:
        bulk_resp = post(saleh_token, "/contacts/claim-bulk", {"contact_ids": remaining_ids})
        count = bulk_resp.get("claimed_count", 0)
        print(f"  Bulk claimed: {count} leads")
        claimed_ids.extend(remaining_ids)
    except Exception as e:
        print(f"  ERROR bulk claiming: {e}")

# Step 9: Verify claimed leads now in active contacts, appended at end
step(9, "Verify claimed leads now appear in active contacts (NEW status)")
time.sleep(0.5)
try:
    active_resp2 = get(saleh_token, "/contacts", {"per_page": 1})
    active_total_after = active_resp2.get("meta", {}).get("total", 0)
    print(f"  Saleh active contacts after claim: {active_total_after}")
    print(f"  Expected increase: +{len(claimed_ids)}")
    
    # Check the specific claimed contacts' new status via DB
    conn = sqlite3.connect("c:/Users/user/Alpha-Pro-Mena-CRM\\backend\\crm.db")
    c = conn.cursor()
    for cid in claimed_ids[:3]:
        c.execute("SELECT first_name, last_name, status, sheet_order FROM contacts WHERE id=?", (cid,))
        row = c.fetchone()
        if row:
            print(f"  {row[0]} {row[1]}: status={row[2]}, sheet_order={row[3]}")
    conn.close()
except Exception as e:
    print(f"  ERROR: {e}")

# Step 10: Verify pool is empty now
step(10, "Verify Saleh's personal pool is now empty")
try:
    pool_after = get(saleh_token, "/contacts", {"pending_claim_only": "true", "per_page": 1})
    pool_after_count = pool_after.get("meta", {}).get("total", 0)
    pool_status = "OK (empty)" if pool_after_count == 0 else f"Still has {pool_after_count} leads"
    print(f"  Saleh's pool after claiming all: {pool_status}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 70)
print("END-TO-END TEST COMPLETE")
print("=" * 70)
