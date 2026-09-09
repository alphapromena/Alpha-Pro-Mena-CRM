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

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
copy ..\.env.example .env        # configure secrets & company email domain

# Run database migrations
.venv\Scripts\alembic upgrade head

# Seed team accounts & demo data
# Provisions the 7 team members (Saleh, Hassan, Amin, Ghaida, Qusai, Aseel, Abdallah)
# with temporary activation credentials and must_change_password=True.
.venv\Scripts\python -m app.seed

# Optional: To safely update/bootstrap all 7 team accounts with the temporary password
# and force must_change_password=True without touching any existing data:
.venv\Scripts\python scripts/bootstrap_team_passwords.py

# Start the API server
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Local development uses SQLite by default (`backend/crm.db`); production uses PostgreSQL (see [Deployment](docs/deployment.md)).

### 2. Frontend Setup

```bash
cd frontend
npm ci
npm run dev
```

The UI is at `http://localhost:5173`; API docs at `http://localhost:8000/api/docs` (when `APP_DEBUG=true`).

---

## 👥 Team Accounts & Authentication Architecture

### Team Members & Assigned Roles
The platform provisions 7 official team accounts using the company email domain configured via `COMPANY_EMAIL_DOMAIN` (default: `alphapromena.com`):
* **Saleh** (`saleh@alphapromena.com`) — `ADMIN`
* **Hassan** (`hassan@alphapromena.com`) — `MANAGER`
* **Amin** (`amin@alphapromena.com`) — `TEAM_LEAD`
* **Ghaida** (`ghaida@alphapromena.com`) — `SALES_USER`
* **Qusai** (`qusai@alphapromena.com`) — `SALES_USER`
* **Aseel** (`aseel@alphapromena.com`) — `SALES_USER`
* **Abdallah** (`abdallah@alphapromena.com`) — `SALES_USER`

### First-Login Password Activation Workflow
1. Team members receive a one-time activation password during seeding (or via manager provisioning).
2. Upon first login with this temporary password, the system detects `must_change_password=true` and immediately redirects to `/set-password`.
3. Dashboard and API access is strictly blocked until the user sets a strong personal password satisfying the password policy:
   * Minimum 10 characters
   * Uppercase, lowercase, number, and special character required
4. Once set, `must_change_password` is cleared and an audit event is logged.

### Email Verification & Resend Cooldown
* **Verification Token**: An expiring 24-hour cryptographic token is generated upon account creation or verification request.
* **Token Security**: Tokens are hashed with SHA-256 before database storage; raw tokens are never persisted.
* **One-Time Use**: Tokens are invalidated immediately upon successful activation.
* **Resend Cooldown**: The UI features an interactive "Resend Verification Email" button with a 60-second cooldown timer and backend rate-limiting (429 Too Many Requests) to prevent spamming.
* **Anti-Enumeration**: Both password-reset and resend endpoints return generic 200 responses to prevent account enumeration attacks.
* **Local Development Mailbox**: In development mode without SMTP, outgoing tokens are logged and can be viewed at `/api/v1/auth/dev-mail`.

---

## 📇 Contact Editing & Full Auditability

* **Clickable Contact Identity**: Clicking any contact name across the CRM navigates directly to the Contact Detail workspace.
* **Edit Profile Drawer/Modal**: Sales reps and managers can update complete profile attributes:
  * Full Name, Job Title / Position, Company, Phone, Secondary Phone, Email, Country, Industry, Lead Owner, Lifecycle Stage, and Notes.
* **Email Correction**: Supports correcting misspelled emails after failed outreach without breaking existing call history or demo relationships.
* **Validation & Unsaved Safeguards**: Real-time email and phone validation with dirty-state warnings before discarding modifications.
* **Granular Audit Log**: Every edit creates immutable audit entries tracking:
  * Acting user and timestamp
  * Field-by-field diff (`old_value` ➔ `new_value`)
  * Diff preview directly in the Unified Activity Timeline

---

## 📊 Mandatory Demo Reporting & Status Filters

### Mandatory Report Rules
Every demo record enforces data integrity:
1. **Summary**: Mandatory non-empty executive overview (`topics_covered` / `summary`).
2. **Conditional Validations**:
   * `INTERESTED_NEXT_STEP`: Requires a defined `next_step` and optional `next_step_due_date`.
   * `POSTPONED`: Requires a detailed postponement `reason` and future `next_step`.
   * `NOT_INTERESTED`: Requires an objection/reason.
   * `CANCELLED`: Requires a cancellation reason.
   * `PENDING`: Requires a clear follow-up action.
3. **Report Badges**: Records are flagged with visual badges:
   * 🟢 **Report Complete**
   * 🟡 **Needs Report** (allows users to open and complete historical or incomplete records)

### 6 Demo Status Filter Tabs
The Demos workspace features tabbed navigation with real-time KPI counts:
* **All Demos**
* **Interested / Next Step**
* **Pending**
* **Postponed**
* **Not Interested**
* **Cancelled**
* Sub-filters for **Needs Report** and **Historical Demos**
* Dynamic search by contact, company, or owner
* Fully synchronized with URL query parameters for bookmarkable and shareable views.

---

## 📜 Historical Demos & Data Ingestion

### Adding Historical Demos
For demos conducted before the CRM deployment:
* Click **"Add Historical Demo"** in the Demos view.
* Captures: Real demo date (`historical_date`), attendees, presenter, topic summary, result, and historical notes.
* Preserves the actual date of the interaction separately from `created_at` (audit timestamp).
* Historical records flow seamlessly into management analytics and timeline views.

### CSV & JSON Batch Import
* Includes downloadable CSV template.
* Interactive 2-step import modal with **Validation Preview (Dry Run)** before database commitment.
* Matches existing contacts by email or company, and detects row-level errors.

---

## 📈 Connected Dashboards

* **Personalized Rep View**:
  * My Total Demos, My Interested, My Pending, My Postponed, My Cancelled, My Demos Needing Reports.
  * Upcoming and overdue next-step alerts.
* **Management & Team View (Admin / Manager / Team Lead)**:
  * Full team demo breakdown and status distribution charts.
  * User performance leaderboard with completed reports and demo velocity.
  * Recent team activity & contact updates timeline.
* **Interactive Navigation**: Clicking any KPI card filters and navigates directly to the matching Demos or Contacts view.

---

## 🧪 Testing & Verification

### Automated Backend Tests
Comprehensive integration and unit test suite (26 tests covering security, tokens, RBAC, demos, and dashboards):
```bash
cd backend
.venv\Scripts\python -m pytest -v
```

### Frontend Production Build
TypeScript validation and Vite production bundle check:
```bash
cd frontend
npm run build
```

---

## ☁️ Deployment & Production Configuration

### Required Production Environment Variables
* `APP_ENV=production`
* `APP_SECRET_KEY`: Minimum 32-character random string (e.g. `openssl rand -hex 32`)
* `JWT_SECRET_KEY`: Minimum 32-character random string
* `DATABASE_URL`: PostgreSQL connection string (with SSL mode)
* `COMPANY_EMAIL_DOMAIN`: Valid production domain (e.g. `alphapromena.com`)
* `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`: Production email provider credentials

Full deployment options for Vercel, Docker, and Linux VM are detailed in [docs/deployment.md](docs/deployment.md).

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
