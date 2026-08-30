"""
End-to-end smoke test: boots the API on a throw-away COPY of the SQLite database and
exercises health, auth (login / me / refresh), RBAC, rate limiting and cron endpoints.

    cd backend
    .venv/Scripts/python -m scripts.smoke_test
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import bcrypt
import httpx

BACKEND = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("SMOKE_PORT", "8011"))
BASE = f"http://127.0.0.1:{PORT}"
CRON = "smoke-secret"


def main() -> int:
    src = BACKEND / "crm.db"
    tmp = BACKEND / "backups" / "smoke.db"
    tmp.parent.mkdir(exist_ok=True)
    shutil.copy2(src, tmp)

    # give one real user a known password ON THE COPY ONLY
    pw = "Smoke-Test-Pass-1"
    con = sqlite3.connect(tmp)
    con.execute("UPDATE users SET password_hash=?, is_locked=0, login_attempts=0 WHERE email='saleh@alphapromena.com'",
                (bcrypt.hashpw(pw.encode(), bcrypt.gensalt(4)).decode(),))
    con.commit(); con.close()

    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{tmp.as_posix()}", "ENABLE_SCHEDULER": "false",
           "CRON_SECRET": CRON, "APP_DEBUG": "false", "LOG_LEVEL": "WARNING", "LOG_FORMAT": "json"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "warning"],
                            cwd=BACKEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # Drain the server's stdout continuously: an unread pipe fills (4 KB on Windows) and blocks the server.
    server_log: list[str] = []
    threading.Thread(target=lambda: [server_log.append(line) for line in proc.stdout], daemon=True).start()
    results = []
    def check(name, ok, detail=""):
        results.append((name, ok, detail)); print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{BASE}/api/health", timeout=1).status_code == 200: break
            except Exception: pass
            if proc.poll() is not None: break
            time.sleep(0.5)
        else:
            raise RuntimeError("API did not start")

        c = httpx.Client(base_url=BASE, timeout=10)
        r = c.get("/api/health"); check("health", r.status_code == 200 and r.json().get("database") == "ok", r.text[:80])
        check("docs hidden when APP_DEBUG=false", c.get("/api/docs").status_code == 404)
        check("unauthenticated /contacts -> 401", c.get("/api/v1/contacts").status_code == 401)
        check("refresh without cookie -> 401", c.post("/api/v1/auth/refresh").status_code == 401)
        check("cron without secret -> 401", c.get("/api/v1/jobs/run-all").status_code == 401)
        r = c.get("/api/v1/jobs/run-all", headers={"Authorization": f"Bearer {CRON}"})
        check("cron run-all with secret", r.status_code == 200 and all(x["status"] == "ok" for x in r.json()["results"]), r.text[:120])
        r = c.get("/api/v1/jobs/nope", headers={"Authorization": f"Bearer {CRON}"}); check("unknown job -> 404", r.status_code == 404)

        codes, timings = [], []
        for _ in range(7):
            t0 = time.perf_counter()
            codes.append(c.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x"}, timeout=60).status_code)
            timings.append(round(time.perf_counter() - t0, 2))
        check("login bad creds -> 401 then rate-limited 429", codes[0] == 401 and 429 in codes, f"{codes} {timings}s")

        c2 = httpx.Client(base_url=BASE, timeout=10, headers={"X-Forwarded-For": "203.0.113.9"})
        r = c2.post("/api/v1/auth/login", json={"email": "saleh@alphapromena.com", "password": pw})
        check("login real user (separate IP) -> 200 + cookies", r.status_code == 200 and "access_token" in r.cookies and "refresh_token" in r.cookies, r.text[:100])
        r = c2.get("/api/v1/auth/me"); check("GET /auth/me with cookie", r.status_code == 200 and r.json().get("role") == "USER", r.text[:100])
        r = c2.get("/api/v1/contacts", params={"per_page": 5}); check("USER can list own contacts", r.status_code == 200 and len(r.json().get("data", [])) > 0, str(r.status_code))
        r = c2.get("/api/v1/users"); check("USER blocked from /users (403)", r.status_code == 403)
        r = c2.post("/api/v1/auth/refresh"); check("refresh with cookie -> new access token", r.status_code == 200 and "access_token" in r.cookies)
        r = c2.post("/api/v1/auth/logout"); check("logout", r.status_code == 200)
        check("after logout /auth/me -> 401", c2.get("/api/v1/auth/me").status_code == 401)
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except Exception: proc.kill()
        if any(not ok for _, ok, _ in results):
            print("---- server log tail ----"); print("".join(server_log)[-3000:])
        try: tmp.unlink()
        except Exception: pass
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
