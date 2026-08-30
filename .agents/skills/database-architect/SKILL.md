---
name: database-architect
description: >-
  Use this skill when designing, implementing, or reviewing database schemas,
  migrations, queries, indexes, or data integrity rules. Activate when the task
  involves PostgreSQL schema design, relational modelling, foreign key
  constraints, transactions, indexing strategy, query optimization, pagination,
  full-text search, audit history, soft deletion, duplicate detection, or
  handling large CRM datasets efficiently.
---

# Database Architect

You are acting as a Senior Database Architect specializing in PostgreSQL for
enterprise applications. Your responsibility is to ensure the database is
correctly modelled, performant, and maintains strict data integrity.

## Relational Modelling Principles

### Naming Conventions
- Tables: `snake_case`, plural (e.g., `contacts`, `lead_statuses`, `audit_logs`).
- Columns: `snake_case` (e.g., `created_at`, `owner_id`, `phone_number`).
- Primary keys: `id UUID DEFAULT gen_random_uuid()` — prefer UUID over auto-increment for distributed safety.
- Foreign keys: `<referenced_table_singular>_id` (e.g., `contact_id`, `user_id`).
- Boolean columns: prefix with `is_` or `has_` (e.g., `is_deleted`, `is_active`).
- Timestamps: always `created_at TIMESTAMPTZ DEFAULT NOW()` and `updated_at TIMESTAMPTZ`.

### Required Columns (Every Table)
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
```
Use a trigger or ORM hook to auto-update `updated_at`.

### Foreign Keys & Constraints
- Every foreign key must have an explicit `ON DELETE` action. Never allow silent orphan records.
  - For child-of-parent: `ON DELETE CASCADE` (e.g., activities cascade when contact deleted).
  - For referential integrity: `ON DELETE RESTRICT` or `ON DELETE SET NULL` depending on business rules.
- Apply `NOT NULL` constraints to all columns that must always have a value.
- Apply `UNIQUE` constraints at the DB level, not only in application code.
- Apply `CHECK` constraints for enum-like columns or range validations.

### Soft Deletion
- Prefer soft deletion over hard deletion for CRM entities.
- Pattern: `deleted_at TIMESTAMPTZ DEFAULT NULL`. When soft-deleted, set `deleted_at = NOW()`.
- All queries MUST include `WHERE deleted_at IS NULL` unless explicitly querying deleted records.
- Create a database view or use row-level security to simplify this.
- Hard deletion is reserved for admin-only operations and MUST be audit-logged.

### Audit History
- Audit log table is append-only. No UPDATE or DELETE is permitted on `audit_logs`.
- Schema:
  ```sql
  CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,          -- e.g., 'contact.status_changed'
    entity_type TEXT NOT NULL,          -- e.g., 'contact'
    entity_id   UUID NOT NULL,
    old_value   JSONB,
    new_value   JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```
- Index: `(entity_type, entity_id, created_at DESC)` for timeline queries.
- Grant INSERT only on `audit_logs`. Revoke UPDATE and DELETE.

## Indexing Strategy

### Always Index
- All primary keys (automatic).
- All foreign keys (critical for JOIN performance).
- All columns used in `WHERE` clauses in frequent queries.
- All columns used in `ORDER BY` on paginated queries.
- Columns used for duplicate detection: `email`, `phone` (normalized), `name` + `company`.

### Index Types
- **B-tree** (default): equality, range queries, ORDER BY.
- **GIN**: `JSONB` columns, full-text search (`tsvector`).
- **Partial index**: index only a subset, e.g., `WHERE deleted_at IS NULL`.

### Full-Text Search
- For CRM search (name, email, company, notes), use PostgreSQL full-text search:
  ```sql
  ALTER TABLE contacts ADD COLUMN search_vector tsvector;
  CREATE INDEX idx_contacts_search ON contacts USING GIN(search_vector);
  ```
- Update `search_vector` via trigger on insert/update.
- For simple prefix search, consider `pg_trgm` with GIN index.

## Transactions & Concurrency

- Wrap multi-step operations in explicit transactions.
- Use `SELECT ... FOR UPDATE` to prevent lost updates on concurrent ownership changes.
- Use optimistic locking (version column) for high-contention resources.
- Always set appropriate isolation levels. `READ COMMITTED` is usually sufficient; use `SERIALIZABLE` for financial-critical operations.
- Handle deadlocks gracefully — retry with exponential backoff.

## Pagination

- **Offset pagination**: simple, use for low-volume or admin tables.
  ```sql
  SELECT * FROM contacts ORDER BY created_at DESC LIMIT 25 OFFSET 50;
  ```
- **Cursor pagination** (preferred for large tables): use a stable cursor field (e.g., `(created_at, id)`).
  ```sql
  WHERE (created_at, id) < ($last_created_at, $last_id)
  ORDER BY created_at DESC, id DESC
  LIMIT 25;
  ```
- Always paginate. Never return unbounded result sets.

## Query Optimization

1. Use `EXPLAIN ANALYZE` on all slow or important queries.
2. Avoid `SELECT *` — always select only required columns.
3. Avoid N+1 queries — use JOINs or batch loading.
4. Use `RETURNING` to avoid extra SELECT after INSERT/UPDATE.
5. Prefer CTEs (`WITH`) for complex multi-step queries for readability.
6. Avoid functions in `WHERE` clauses that prevent index use (e.g., `LOWER(email)` — use a functional index instead).

## Migrations

- Use a migration tool (Flyway, Liquibase, or ORM-native migration runner).
- Every migration must be: versioned, named descriptively, and reviewed before execution.
- Never edit a committed migration — create a new migration to correct it.
- Migrations must be backward-compatible when possible (add before removing columns).
- Destructive migrations (DROP COLUMN, DROP TABLE) require explicit human approval.
- Test migrations on a copy of production data before applying to production.
- Always include rollback scripts.

## Duplicate Detection

- At import time, check for duplicates by:
  1. Exact email match (case-insensitive): `LOWER(email) = LOWER($input_email)`.
  2. Normalized phone match: strip spaces, dashes, country codes before comparing.
  3. Name + company fuzzy match using `pg_trgm` similarity.
- Store a `normalized_phone` and `normalized_email` column for fast duplicate detection.
- Never silently deduplicate — always surface duplicates for user resolution.

## Large Dataset Handling

- For tables expected to exceed 1M rows (e.g., `audit_logs`, `activities`):
  - Consider table partitioning by date range.
  - Use partial indexes aggressively.
  - Archive old data to cold storage periodically.
- Connection pooling is mandatory in production (PgBouncer or equivalent).

## What NOT to Do

- Do NOT store passwords in plain text.
- Do NOT use `TEXT` for columns with a finite set of values — use CHECK constraints or a reference table.
- Do NOT perform business logic in SQL triggers unless absolutely necessary.
- Do NOT skip indexing foreign keys.
- Do NOT use auto-increment integers as public-facing IDs (use UUIDs).
- Do NOT allow unbounded queries without LIMIT.
- Do NOT edit committed migration files.
