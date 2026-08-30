---
name: convex-architecture-reviewer
description: >-
  Use this skill as an authoritative reference for reactive data models,
  real-time state consistency, client-side optimistic updates, performance
  profiling, and integration testing patterns. NOTE: This CRM has an established
  FastAPI architecture; this skill is for architectural and performance review
  knowledge only — DO NOT migrate the application to Convex.
---

# Convex Reactive Architecture & Performance Standards

This skill provides patterns for real-time responsiveness, optimistic data reconciliation, and mutation safety in enterprise web apps.

## Key Principles

1. **Optimistic UI Consistency**:
   - Provide instant UI feedback on critical sales actions (call logging, status change) with rollback guards on network errors.

2. **Deterministic Mutation Pipelines**:
   - Mutations must have single-responsibility execution paths that prevent partial state writes.

3. **Query Deduplication & Caching**:
   - Deduplicate in-flight GET requests and cache static lookup data (teams, users, pipeline stages).
