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

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run migrations & seed data
python -m app.seed

# Start backend server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install npm dependencies
npm install

# Start Vite dev server
npm run dev
```

The frontend will be live at `http://localhost:5173`.

---

## 🔐 Default Development Credentials

| Role | Email | Password | Allowed Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@alphapro.com` | `Admin123!` | Full System Control, Users, Teams, Distribution, Audit Logs |
| **Manager** | `manager@alphapro.com` | `Manager123!` | Management Analytics, Performance Reports, Lead Reassignment |
| **Team Leader**| `leader@alphapro.com` | `Leader123!` | Team Outreach View, Task Delegation |
| **Sales Agent**| `saleh@alphapro.com` | `Sales123!` | My Work Daily Workstation, Assigned Leads, Call Logging |

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

## 🐳 Docker Deployment

```bash
docker compose up -d --build
```
* **Frontend**: `http://localhost:5173`
* **Backend API**: `http://localhost:8000`
* **API Docs**: `http://localhost:8000/api/docs`

---

## 📚 Technical Documentation Index

* [Architecture Guide](docs/architecture.md)
* [Database Schema & Integrity](docs/database.md)
* [REST API Catalog](docs/api.md)
* [Security Engineering & RBAC](docs/security.md)
* [CRM Business Rules & Workflows](docs/crm-business-rules.md)
* [Google Sheets Integration Guide](docs/google-sheets-integration.md)
* [Deployment & Docker Guide](docs/deployment.md)
* [Testing & QA Strategy](docs/testing.md)
