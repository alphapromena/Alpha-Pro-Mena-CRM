# REST API Specification — Alpha Pro MENA CRM

All APIs are versioned under `/api/v1` with consistent JSON envelopes and strict HTTP status semantics.

## 1. Authentication & Session

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Public (Rate Limited) | Authenticates user; sets HttpOnly access & refresh cookies |
| `POST` | `/api/v1/auth/logout` | Authenticated | Clears auth session cookies |
| `POST` | `/api/v1/auth/refresh` | Authenticated | Exchanges refresh token for new access token |
| `GET` | `/api/v1/auth/me` | Authenticated | Returns current profile, role, and team |
| `POST` | `/api/v1/auth/change-password`| Authenticated | Updates user password |

## 2. Contacts & Outreach

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/contacts` | Authenticated (Scoped) | Paginated contacts with multi-column filters |
| `POST` | `/api/v1/contacts` | Authenticated | Creates a new contact with duplicate detection |
| `GET` | `/api/v1/contacts/{id}` | Authenticated | Retrieves detailed contact record |
| `PATCH` | `/api/v1/contacts/{id}` | Authenticated | Updates contact fields |
| `PATCH` | `/api/v1/contacts/{id}/status` | Authenticated | Enforces state machine status transition |
| `POST` | `/api/v1/contacts/{id}/dnc` | Authenticated | Marks contact as Do Not Contact (terminal state) |
| `POST` | `/api/v1/contacts/{id}/assign` | Team Leader+ | Reassigns contact owner with audit logging |
| `GET` | `/api/v1/contacts/{id}/timeline` | Authenticated | Unified chronological activity timeline |
| `DELETE`| `/api/v1/contacts/{id}` | Manager+ | Soft-deletes contact |

## 3. Calls & Activities

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/calls` | Authenticated | Logs call attempt, updates contact, fires automation |
| `GET` | `/api/v1/calls` | Authenticated | Queries logged call history |

## 4. Tasks, Recalls & Follow-ups

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/tasks` | Authenticated | Lists open, in-progress, or overdue tasks |
| `POST` | `/api/v1/tasks` | Authenticated | Creates a new task |
| `POST` | `/api/v1/tasks/{id}/complete` | Authenticated | Marks task as completed with notes |
| `GET` | `/api/v1/recalls` | Authenticated | Lists customer-requested callbacks |
| `POST` | `/api/v1/recalls/{id}/complete` | Authenticated | Marks recall as completed |
| `GET` | `/api/v1/follow-ups` | Authenticated | Lists 24-hour follow-up actions |
| `GET` | `/api/v1/no-answer` | Authenticated | Lists leads in the multi-attempt retry queue |

## 5. Admin & Google Sheets

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/admin/leads/unassigned` | Manager+ | Inspects new leads pool awaiting assignment |
| `POST` | `/api/v1/admin/leads/distribute` | Manager+ | Executes lead distribution strategies |
| `GET` | `/api/v1/integrations/google-sheets/configs` | Admin | Lists Google Sheet sync configurations |
| `POST` | `/api/v1/integrations/google-sheets/sync/{id}` | Admin | Triggers manual Google Sheet sync |
| `GET` | `/api/v1/admin/audit-logs` | Manager+ | Read-only security audit trail |
| `GET` | `/api/v1/reports/dashboard` | Manager+ | High-level executive KPI metrics |
| `GET` | `/api/v1/reports/user-performance` | Manager+ | Comparative sales agent performance |
