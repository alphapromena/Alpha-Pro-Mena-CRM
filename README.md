# Alpha Pro MENA — CRM & Sales Outreach Management System

A high-performance, enterprise-grade Customer Relationship Management (CRM) and Sales Outreach platform tailored specifically for **Alpha Pro MENA**.

---

## 🌟 Executive Summary

* **Platform Purpose**: High-velocity B2B sales outreach, multi-channel lead tracking, Google Sheets data ingestion, automated task generation, recall scheduling, No Answer retries, and executive management reporting.
* **Core Philosophy**: Optimized around the salesperson's daily workflow — answering **"Who should I contact next, and what should I do?"**
* **Target Scale**: Supports hundreds of thousands of contacts, multi-tier RBAC, full auditability, and fast search indexing.

---

## 🏛️ Architecture Overview

```
               ┌─────────────────────────────────────────┐
               │    React 18 + TypeScript (Vite)         │
               │    TanStack Query + Zustand + CSS Tokens│
               └────────────────────┬────────────────────┘
                                    │ HTTP / JSON (HttpOnly Cookies)
               ┌────────────────────▼────────────────────┐
               │         FastAPI Async Backend           │
               │   Auth / RBAC / Services / Repositories │
               └─────────┬─────────────────────┬─────────┘
                         │                     │
      ┌──────────────────▼──────┐    ┌─────────▼───────────────┐
      │ PostgreSQL 15 Database  │    │  APScheduler Job Engine │
      │ UUID PKs, GIN TSVector  │    │  Overdue / Sheets Sync  │
      └─────────────────────────┘    └─────────────────────────┘
```

---

## 🚀 Quick Start (Local Development)

The quickest way on Windows is **`Start CRM.bat`** — it starts the API and the UI from wherever the folder lives.
Manual steps:

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
copy ..\.env.example .env        # set APP_SECRET_KEY and JWT_SECRET_KEY (32+ chars)

# First run only: creates the SQLite schema (backend/crm.db) and seed users,
# printing their temporary passwords ONCE.
.venv\Scripts\python -m app.seed

.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Local development uses SQLite by default; production uses PostgreSQL (see [Deployment](docs/deployment.md)).

### 2. Frontend

```bash
cd frontend
npm ci
npm run dev
```

The UI is at `http://localhost:5173`; API docs at `http://localhost:8000/api/docs` (when `APP_DEBUG=true`).

---

## 🔐 Credentials

There are **no built-in passwords**. `python -m app.seed` generates a random temporary password for every
account (or uses `ADMIN_PASSWORD` from `.env` for the admin) and prints them once. Rotate all passwords on an
existing database with `python -m scripts.rotate_passwords --apply`. Users change their own password under
Settings.

---

## 🧪 Testing

### Backend Unit & Integration Tests

```bash
cd backend
pytest tests/ -v
```

### Playwright End-to-End Tests

```bash
npx playwright test
```

---

## ☁️ Deployment

* **Vercel** (recommended): static Vite frontend + FastAPI serverless function + hosted PostgreSQL, background
  jobs via Vercel Cron. Full walkthrough, environment variables and data migration in
  [docs/deployment.md](docs/deployment.md).
* **Docker Compose**: `docker compose up -d --build` → UI `:5173`, API `:8000`, PostgreSQL `:5432`.

---

## 📚 Technical Documentation Index

* [Architecture Guide](docs/architecture.md)
* [Database Schema & Integrity](docs/database.md)
* [REST API Catalog](docs/api.md)
* [Security Engineering & RBAC](docs/security.md)
* [CRM Business Rules & Workflows](docs/crm-business-rules.md)
* [Google Sheets Integration Guide](docs/google-sheets-integration.md)
* [Deployment Guide (Vercel / Docker / local)](docs/deployment.md)
* [Testing & QA Strategy](docs/testing.md)
