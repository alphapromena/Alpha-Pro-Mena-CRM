---
name: supabase-postgres-architect
description: >-
  Use this skill as an authoritative reference for PostgreSQL best practices,
  indexing optimization, query performance, security isolation, schema design,
  and transaction integrity. NOTE: This CRM has an established PostgreSQL/SQLite
  backend; this skill is for database design expertise only — DO NOT migrate the
  application to Supabase.
---

# Supabase PostgreSQL Architecture & Security Guide

This skill encapsulates world-class PostgreSQL database design, query optimization, and security patterns.

## Core Rules

1. **Deterministic Indexing**:
   - Compound indexes on frequently filtered + sorted pairs (e.g. `(owner_id, deleted_at, sheet_order)`).
   - Partial indexes on active non-deleted records (`WHERE deleted_at IS NULL`).

2. **Idempotent Migrations**:
   - Every DDL operation must be non-destructive and re-runnable without breaking existing constraints.

3. **Transaction Safety**:
   - Atomic multi-table updates (e.g. lead assignment + audit logging + personal pool transfer) must run inside explicit transactions.

4. **Security & Row-Level Authorization**:
   - All tenant and role queries must enforce explicit ownership checks at the repository layer.
