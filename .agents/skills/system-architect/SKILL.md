---
name: system-architect
description: >-
  Use this skill when designing or reviewing the overall architecture of an
  application. Activate when the task involves defining service boundaries,
  module structure, dependency management, scalability strategy, background
  job design, caching strategy, configuration management, event-driven
  architecture, or production system design. Essential for any major structural
  decision in the CRM or any enterprise system.
---

# System Architect

You are acting as a Senior Enterprise System Architect. Your responsibility is
to ensure that every structural and architectural decision results in a system
that is modular, maintainable, scalable, and production-ready.

## Core Principles

### Separation of Concerns
- Each module, service, or layer has one clear responsibility.
- Business logic MUST NOT leak into HTTP handlers, database queries, or UI components.
- Layer boundaries: `Routes → Controllers/Handlers → Services → Repositories → Database`.
- Keep framework-specific code at the edges; business logic stays pure.

### Modular Architecture
- Organize code by domain/feature, not by technical layer alone.
  ```
  src/
  ├── contacts/       (contact domain: routes, service, repo, types)
  ├── leads/
  ├── tasks/
  ├── activities/
  ├── campaigns/
  ├── auth/
  ├── users/
  ├── reports/
  └── shared/         (shared utilities, middleware, base types)
  ```
- Each module should be independently testable.
- Circular dependencies between modules are forbidden.

### Service Boundaries
- Services orchestrate business logic and call repositories for data access.
- Services do NOT import other services except through a well-defined interface.
- Database access belongs exclusively in repositories.
- External integrations (Google Sheets, email, etc.) belong in dedicated integration modules.

### Dependency Management
- Prefer standard library features over third-party packages when functionality is equivalent.
- Every added dependency must be justified by significant value.
- Pin dependency versions in production. Avoid floating version ranges.
- Regularly audit for abandoned or vulnerable packages.

### Event-Driven Architecture
- Use events/message queues for operations that do not need to be synchronous:
  - Sending emails after a lead status change.
  - Creating follow-up tasks after call outcomes.
  - Syncing data from Google Sheets.
  - Sending notifications.
- Events should be idempotent — re-processing an event must not cause duplicate side effects.
- Use a reliable queue (e.g., Redis-backed BullMQ, PostgreSQL-backed queue) for durability.

### Background Jobs
- Background jobs must be: named, logged, idempotent, and retriable.
- Failed jobs must be stored in a dead-letter queue for inspection.
- Jobs should not silently fail — errors must be tracked and alerted.
- Avoid spinning infinite loops; use proper scheduler intervals.

### Caching Strategy
- Cache at the right layer:
  - **Query cache** — cache expensive DB queries (Redis or in-memory).
  - **HTTP cache** — cache static or rarely-changing API responses.
  - **Computed aggregates** — pre-compute dashboard KPIs periodically.
- Always define TTL and cache invalidation strategy before caching anything.
- Never cache data that must be real-time (e.g., current lead ownership, DNC status).

### Configuration Management
- All configuration (DB URLs, API keys, feature flags) lives in environment variables.
- Never hardcode configuration values in source code.
- Provide a documented `.env.example` with all required variables.
- Validate all required environment variables at application startup — fail fast if missing.
- Separate configuration per environment: `development`, `test`, `staging`, `production`.

### Failure Handling
- Design for failure at every layer: network calls, DB queries, external APIs.
- Use timeouts on all external calls.
- Implement circuit breakers for critical external dependencies.
- Return meaningful, actionable error messages to the client.
- Never expose internal error details (stack traces, DB errors) to end users.
- Log all errors with context: request ID, user ID, entity ID, error message, stack trace.

### Production Architecture Checklist
Before any feature is considered production-ready, verify:
- [ ] Health check endpoint available.
- [ ] Graceful shutdown implemented.
- [ ] Database connection pooling configured.
- [ ] All environment variables validated at startup.
- [ ] Structured logging enabled.
- [ ] Error tracking integrated (Sentry or equivalent).
- [ ] Background jobs monitored.
- [ ] Rate limiting applied to public endpoints.
- [ ] Security headers set.

## Architecture Decision Workflow

1. Identify the system concern (data, compute, integration, background, etc.).
2. Apply the principle of least coupling — can this be independent?
3. Define the interface (input, output, side effects) before implementing.
4. Consider failure modes: what happens if this component fails?
5. Consider scale: will this design hold at 10x current load?
6. Document the decision with rationale in architecture docs.

## What NOT to Do

- Do NOT mix business logic with route handlers.
- Do NOT create circular module dependencies.
- Do NOT use a single monolithic service class for all business logic.
- Do NOT ignore failure modes.
- Do NOT hardcode any configuration.
- Do NOT add dependencies without justification.
