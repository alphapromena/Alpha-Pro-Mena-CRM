import urllib.request

assets = [
    "http://localhost:5173/videos/wall.mp4",
    "http://localhost:5173/videos/wall.webm",
    "http://localhost:5173/favicon.svg",
    "http://localhost:5173/logo-brand-dark.svg",
    "http://localhost:5173/logo-brand-light.svg",
]

print("Checking static asset HTTP availability on Vite dev server:")
for url in assets:
    try:
        req = urllib.request.Request(url, headers={"Range": "bytes=0-1024"})
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type")
            status = resp.status
            print(f"  [OK {status}] {url} -> Content-Type: {content_type}")
    except Exception as e:
        print(f"  [FAIL] {url} -> {e}")
