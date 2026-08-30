# System Architecture — Alpha Pro MENA CRM

## 1. Architectural Principles

The Alpha Pro MENA CRM architecture follows a clean, service-oriented modular pattern adhering strictly to **Domain-Driven Design (DDD)** and **Separation of Concerns**.

### High-Level Layers

```
[ HTTP Client (Browser) ]
         │
         ▼
[ FastAPI App Engine ]
  ├── RequestContextMiddleware (Injects UUID request_id, security headers)
  ├── Structured Logger (JSON in production, Colored in dev)
  ├── CORS & Rate Limiter (SlowAPI)
  │
  ├── Routers (API Endpoints & Request Parameter Validation)
  │       │
  │       ▼
  ├── Service Layer (Business rules, state machine, permission validation)
  │       │
  │       ▼
  ├── Repositories / SQLAlchemy ORM (Data access, transactions, queries)
  │       │
  │       ▼
  └── PostgreSQL 15 Engine (Relational data, GIN Trigram Search, JSONB)
```

## 2. Frontend Component Architecture

* **Directory Structure**: Feature-based organization (`features/contacts/`, `features/my-work/`, `features/dashboard/`, etc.).
* **State Segregation**:
  * **Server State**: Managed exclusively via `@tanstack/react-query` with optimistic cache invalidation.
  * **UI / Client State**: Managed via lightweight `zustand` stores.
* **Design Token Integration**: Pure CSS variables (`tokens.css`) defining authoritative Alpha Pro MENA design tokens. No hardcoded hex values across components.

## 3. Background Processing & Scheduling

* **Engine**: APScheduler integrated directly within the FastAPI application lifespan.
* **Durability & Idempotency**:
  * Jobs are recorded in the database before execution.
  * All automation actions compute deterministic `sha256(rule_id + entity_id + trigger_event)` idempotency hashes to prevent duplicate task execution.
