import urllib.request, json

API = "http://127.0.0.1:8000/api/v1"

def api_login(email, password="<set-password>"):
    data = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(f"{API}/auth/login", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]

def api_get(token, path):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

token = api_login("saleh@alphapromena.com")
data = api_get(token, "/contacts?page=1&per_page=2&sort_by=sheet_order&sort_dir=asc")
print("Keys:", list(data.keys()))
print("Full response sample:")
d2 = dict(data)
d2['items'] = d2.get('items', d2.get('contacts', []))[:1]
print(json.dumps(d2, indent=2, default=str)[:2000])
