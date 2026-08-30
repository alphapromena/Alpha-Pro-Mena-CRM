# Deployment Guide

Three supported ways to run the CRM:

| Mode | Frontend | Backend | Database | Background jobs |
| :--- | :--- | :--- | :--- | :--- |
| **Local dev** (`Start CRM.bat`) | Vite dev server :5173 | Uvicorn :8000 | SQLite `backend/crm.db` | APScheduler in-process |
| **Docker Compose** | Vite dev server (or Nginx build) | Uvicorn container | PostgreSQL 15 container | APScheduler in-process |
| **Vercel** (production) | Static Vite build on the CDN | FastAPI as a Python serverless function (`api/index.py`) | Hosted PostgreSQL (Neon / Supabase) | Vercel Cron → `/api/v1/jobs/run-all` |

---

## 1. Vercel (production)

### How the pieces fit

```
https://<project>.vercel.app
   ├─ /            → frontend/dist  (static, SPA fallback to index.html)
   └─ /api/*       → api/index.py   (FastAPI, imports backend/app)
                        └─ DATABASE_URL → PostgreSQL
Vercel Cron  ──GET /api/v1/jobs/run-all (Bearer CRON_SECRET)──▶ overdue tasks, recall reminders, sheets sync
```

Everything is configured in [`vercel.json`](../vercel.json). The API and the UI share one origin, so the
HttpOnly auth cookies work without any CORS configuration.

### Prerequisites

1. A PostgreSQL database. Either:
   * **Neon via the Vercel Marketplace** (Vercel dashboard → Storage → Create → Neon). It injects `DATABASE_URL`
     / `POSTGRES_URL` into the project automatically; or
   * **Supabase**: use the *Transaction pooler* connection string (port `6543`, host `*.pooler.supabase.com`).
     The backend detects pooler hosts and disables prepared statements automatically.
2. The GitHub repository connected to a Vercel project (Root Directory = repository root, Framework Preset = *Other*).
3. Secrets generated locally:
   ```bash
   openssl rand -hex 32   # APP_SECRET_KEY
   openssl rand -hex 32   # JWT_SECRET_KEY
   openssl rand -hex 32   # CRON_SECRET
   ```

### Environment variables (Project → Settings → Environment Variables)

| Key | Value |
| :--- | :--- |
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `APP_SECRET_KEY` | 64-hex random |
| `JWT_SECRET_KEY` | 64-hex random |
| `CRON_SECRET` | 64-hex random (Vercel sends it as the cron bearer token) |
| `DATABASE_URL` | PostgreSQL connection string (skip if the Neon integration injects it) |
| `FRONTEND_URL` | `https://<project>.vercel.app` |
| `CORS_ORIGINS` | `https://<project>.vercel.app` |
| `LOG_FORMAT` | `json` |
| `GOOGLE_SERVICE_ACCOUNT_*` | only if Google Sheets sync is used |

`ENABLE_SCHEDULER` must stay unset/false on Vercel (auto-detected) — a serverless function has no
resident process to run APScheduler in.

### First deploy — step by step

```bash
# 0. (once) make sure the repo is private if it must stay so
gh repo edit alphapromena/Alpha-Pro-Mena-CRM --visibility private

# 1. Create the schema + copy the live SQLite data into PostgreSQL
cd backend
set TARGET_URL=postgresql://...            # PowerShell: $env:TARGET_URL="postgresql://..."
.venv/Scripts/python -m scripts.migrate_sqlite_to_postgres          # dry run – shows table counts
.venv/Scripts/python -m scripts.migrate_sqlite_to_postgres --apply  # copies data, stamps alembic head

# 2. Push to GitHub → Vercel builds automatically
git push -u origin main
#    or from the CLI:  vercel --prod

# 3. Verify
curl https://<project>.vercel.app/api/health          # {"status":"ok","database":"ok"}
curl -H "Authorization: Bearer $CRON_SECRET" https://<project>.vercel.app/api/v1/jobs/run-all

# 4. Rotate every user's password (all current ones are the old defaults)
set DATABASE_URL=postgresql://...
.venv/Scripts/python -m scripts.rotate_passwords --apply
```

### Cron schedule and plan limits

`vercel.json` runs `/api/v1/jobs/run-all` every 15 minutes. **Vercel Hobby only allows one run per day** —
on Hobby change the schedule to e.g. `0 6 * * *` (overdue-task and recall notifications then arrive once a
day) or use a Pro team. Individual jobs can also be triggered manually:
`/api/v1/jobs/overdue-tasks`, `/api/v1/jobs/recall-reminders`, `/api/v1/jobs/sheets-sync`.

### Schema changes after go-live

Migrations are Alembic-managed (`backend/alembic/versions/`). After changing a model:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
set DATABASE_URL=postgresql://...   # production
alembic upgrade head
```

### Troubleshooting

| Symptom | Cause / fix |
| :--- | :--- |
| `/api/health` → `"database":"unreachable"` | `DATABASE_URL` missing or wrong. For Supabase use the pooler string with `?sslmode=require`. |
| Function crashes on start with `APP_SECRET_KEY must be at least 32 characters` | Secrets too short; regenerate with `openssl rand -hex 32`. |
| `SQLite is not supported in production` | `DATABASE_URL` still points at `sqlite+aiosqlite`. |
| Cron returns 403 | `CRON_SECRET` not set in Vercel env. |
| Cron returns 401 | Vercel's bearer token differs from `CRON_SECRET` (redeploy after changing env vars). |
| Login works but session dies after 15 min | Cookies blocked by a mismatched domain — `FRONTEND_URL` and the site must be the same origin. |
| Build fails at `tsc` | Run `cd frontend && npm run build` locally; the same TypeScript errors will show. |

---

## 2. Docker Compose

```bash
cp .env.example backend/.env            # then edit secrets
docker compose up -d --build
```

Services: `postgres` (15-alpine, persistent volume), `backend` (runs `alembic upgrade head`, seeds, then Uvicorn
with `--reload`), `frontend` (Vite dev server; build with `target: production` for the Nginx image that also
proxies `/api` to the backend). Ports: UI 5173, API 8000, Postgres 5432.

## 3. Local development (Windows)

`Start CRM.bat` launches both servers relative to its own folder — the project can live anywhere.

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
copy ..\.env.example .env                 # edit APP_SECRET_KEY / JWT_SECRET_KEY
.venv\Scripts\python -m app.seed          # first run only – prints temporary passwords once
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

cd ../frontend
npm ci
npm run dev
```

Useful checks:

```bash
cd backend
.venv/Scripts/python -m pytest                     # unit + integration tests
.venv/Scripts/python -m scripts.smoke_test         # boots the API on a copy of the DB and exercises auth/RBAC/cron
.venv/Scripts/python -m scripts.fix_db_integrity   # reports orphan rows; --apply repairs (backs up first)
```

## 4. Production checklist

* [ ] Repository visibility matches expectations (it contains staff emails).
* [ ] `APP_ENV=production`, `APP_DEBUG=false`, 32+ char secrets, `CRON_SECRET` set.
* [ ] PostgreSQL provisioned; data migrated; `/api/health` reports `database: ok`.
* [ ] `scripts.rotate_passwords --apply` run — no account still uses `Sales123!` / `Manager123!` / `TeamLead123!`.
* [ ] Cron schedule matches the Vercel plan.
* [ ] Database backups enabled at the provider (Neon/Supabase both offer point-in-time recovery).
