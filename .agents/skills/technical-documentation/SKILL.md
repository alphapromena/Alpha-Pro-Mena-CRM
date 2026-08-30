---
name: technical-documentation
description: >-
  Use this skill when creating or updating technical documentation for the CRM
  system. Activate when the task involves writing architecture documentation,
  API documentation, database schema documentation, environment setup
  instructions, deployment guides, or documenting important business rules and
  decisions. Good documentation is as important as good code.
---

# Technical Documentation Engineer

You are acting as a Senior Technical Writer and Engineer. Your responsibility
is to ensure the CRM system has comprehensive, accurate, and maintainable
documentation that enables any developer to understand, set up, and contribute
to the system.

## Documentation Types

### 1. Architecture Documentation

**Location**: `docs/architecture/`

Required documents:
- `overview.md` — System overview: what the CRM does, who uses it, high-level architecture diagram.
- `backend.md` — Backend architecture: layers, module structure, key patterns.
- `frontend.md` — Frontend architecture: component structure, state management, data fetching.
- `database.md` — Database schema overview, key relationships, migration strategy.
- `integrations.md` — External integrations (Google Sheets), auth providers, email.
- `security.md` — Security architecture: auth model, RBAC, key security decisions.
- `decisions/` — Architecture Decision Records (ADRs) — one file per major decision.

**Architecture Diagram** (Mermaid):
```mermaid
graph TD
  FE[React Frontend] --> API[Node.js API]
  API --> DB[(PostgreSQL)]
  API --> Cache[Redis Cache]
  API --> Queue[Job Queue]
  Queue --> Workers[Background Workers]
  Workers --> Sheets[Google Sheets API]
  Workers --> Email[Email Service]
  API --> Auth[Auth Middleware]
```

### 2. API Documentation

**Format**: OpenAPI 3.x specification (`docs/api/openapi.yaml`)

Every endpoint must document:
```yaml
/contacts/{id}:
  get:
    summary: Get a contact by ID
    description: Returns the full contact record. Sales users can only access their own contacts.
    security:
      - BearerAuth: []
    parameters:
      - name: id
        in: path
        required: true
        schema: { type: string, format: uuid }
    responses:
      '200':
        description: Contact found
        content:
          application/json:
            schema: { $ref: '#/components/schemas/Contact' }
      '403': { description: Access denied }
      '404': { description: Contact not found }
```

Optionally generate interactive docs with Swagger UI at `/api/docs` (development only).

### 3. Database Documentation

**Location**: `docs/database/`

- `schema.md` — Table-by-table documentation.
- `relationships.md` — Entity relationship diagram (ERD).
- `migrations.md` — Migration strategy, naming conventions, how to create migrations.
- `indexes.md` — Key indexes and the queries they support.

**Table Documentation Template**:
```markdown
## contacts

Stores all CRM contacts (individuals).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| first_name | TEXT | No | Contact's first name |
| last_name | TEXT | Yes | Contact's last name |
| email | TEXT | Yes | Email address (unique, case-insensitive) |
| status | TEXT | No | Lead status (see LeadStatus enum) |
| owner_id | UUID | Yes | FK → users.id — assigned sales user (null = unassigned pool) |
| deleted_at | TIMESTAMPTZ | Yes | Soft deletion timestamp (null = active) |
| created_at | TIMESTAMPTZ | No | Record creation time (UTC) |
| updated_at | TIMESTAMPTZ | No | Last modification time (UTC) |

**Indexes**: `idx_contacts_email`, `idx_contacts_owner`, `idx_contacts_status`, `idx_contacts_search`
**Soft delete**: Filter `WHERE deleted_at IS NULL` for active contacts.
```

### 4. Setup & Environment Documentation

**Location**: `README.md` (root) and `docs/setup/`

`README.md` must include:
```markdown
# CRM System

## Quick Start

### Prerequisites
- Node.js 20+
- PostgreSQL 15+
- Redis (if using BullMQ)

### Setup
1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in all required values.
3. Install dependencies: `npm install`
4. Run database migrations: `npm run db:migrate`
5. Seed development data: `npm run db:seed`
6. Start development server: `npm run dev`
7. Frontend available at: http://localhost:5173
8. API available at: http://localhost:3000

### Environment Variables
See `.env.example` for all required variables with descriptions.

### Common Commands
| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run test` | Run unit + integration tests |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run db:migrate` | Run pending migrations |
| `npm run db:rollback` | Rollback last migration |
| `npm run lint` | Run linter |
| `npm run typecheck` | TypeScript type check |
```

### 5. Business Rules Documentation

**Location**: `docs/business-rules/`

Document every non-obvious business rule that affects implementation:

```markdown
## Lead Status Machine

### Valid Transitions

| From | To | Rules |
|------|----|-------|
| NEW | CONTACTED | Any activity logged |
| CONTACTED | IN_PROGRESS | |
| IN_PROGRESS | DEMO_SCHEDULED | |
| ANY | DO_NOT_CONTACT | Manager/Admin only |
| ANY | LOST | |
| DO_NOT_CONTACT | (blocked) | Terminal state. No further transitions. |

### Status Change Rules
- All transitions must be validated server-side.
- Every status change creates an audit log entry.
- Only Manager/Admin can set DO_NOT_CONTACT.
```

### 6. Architecture Decision Records (ADRs)

Document every major architectural decision:

**Template** (`docs/decisions/ADR-001-session-strategy.md`):
```markdown
# ADR-001: Cookie-Based Sessions over JWT

**Date**: 2025-01-15
**Status**: Accepted

## Context
We needed to choose between cookie-based sessions and JWTs for authentication.

## Decision
We chose cookie-based sessions stored in Redis.

## Rationale
- Instant revocation (JWT can't be invalidated before expiry without a blocklist).
- Simpler security model for an internal web app.
- No localStorage risk (XSS).

## Consequences
- Requires Redis for session storage in production.
- Sessions are invalidated on server restart unless Redis is persistent.
```

## Documentation Maintenance Rules

- Update documentation in the SAME PR as the code change.
- Documentation for an API must be written before the API is merged.
- Architecture diagrams must be kept in sync with the actual implementation.
- When a business rule changes, update `docs/business-rules/` immediately.
- Outdated documentation is worse than no documentation — mark stale sections with `> [!WARNING] This section may be outdated`.

## What NOT to Do

- Do NOT write documentation that describes HOW the code works (read the code for that).
- DO write documentation that describes WHY decisions were made.
- Do NOT skip documentation when "under time pressure" — it's always the right time.
- Do NOT put secrets or credentials in documentation files.
- Do NOT document aspirational architecture — only what currently exists.
