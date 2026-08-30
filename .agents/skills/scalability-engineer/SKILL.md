---
name: scalability-engineer
description: >-
  Use this skill when designing features or reviewing architecture for
  scalability. Activate when the task involves handling growing data volumes,
  increasing user concurrency, improving system throughput, designing for
  horizontal scaling, planning database growth, or ensuring the CRM can
  support 10x–100x current load without architectural rework.
---

# Scalability Engineer

You are acting as a Senior Scalability Engineer. Your responsibility is to
ensure the CRM architecture can scale gracefully as the number of contacts,
users, calls, activities, and background jobs grows significantly over time.

## Scalability Targets (Design For)

| Metric | Current | Design Target |
|--------|---------|--------------|
| Contacts | < 10,000 | 1,000,000+ |
| Daily call logs | < 500 | 50,000+ |
| Active users | < 50 | 500+ |
| Background jobs/day | < 1,000 | 100,000+ |
| Concurrent API requests | < 20 | 500+ |
| Audit log entries/month | < 100,000 | 10,000,000+ |

## Database Scalability

### Indexing for Scale
Indexes that become critical at scale:
```sql
-- Partial indexes (smaller, faster than full-column indexes)
CREATE INDEX idx_contacts_active ON contacts(created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_leads_unassigned ON contacts(created_at DESC)
  WHERE owner_id IS NULL AND deleted_at IS NULL;

CREATE INDEX idx_tasks_overdue ON tasks(due_date ASC)
  WHERE completed_at IS NULL AND due_date < NOW();
```

### Table Partitioning (For High-Volume Tables)
Tables that will grow to 100M+ rows should be partitioned:
```sql
-- Partition audit_logs by month
CREATE TABLE audit_logs (
  ...
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_logs_2025_01 PARTITION OF audit_logs
  FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- Create new partition each month via scheduled job
```

Tables to consider partitioning:
- `audit_logs` — by month.
- `activities` (calls, emails) — by month.
- `automation_executions` — by month.

### Read Replicas
When read traffic becomes a bottleneck:
- Route read-heavy queries (reports, dashboards, search) to read replicas.
- Keep write operations on the primary.
- Implement in the repository layer:
  ```typescript
  class ContactRepository {
    constructor(
      private writeDb: Database,
      private readDb: Database  // Read replica
    ) {}

    async findById(id: string) { return this.readDb.query(...); }
    async create(data: CreateContactInput) { return this.writeDb.query(...); }
  }
  ```

### Connection Pooling at Scale
```
Development:  Direct PostgreSQL connection
Staging:      PgBouncer (transaction mode), pool size 10
Production:   PgBouncer (transaction mode), pool size 20 per app instance
              If multi-instance: connection count = instances × 20
```

## Application Scalability

### Horizontal Scaling Design
The application must be stateless (horizontally scalable):
- No in-process session storage (use Redis or DB).
- No in-process job queues (use Redis/BullMQ or pg-boss).
- No in-process rate limiting (use Redis-based rate limiting).
- No in-process cache that must be shared (use Redis).

Any state that must survive a process restart goes to external storage.

### Caching for Scale
Caches that become critical at scale:

```typescript
// Cache expensive aggregations
const CACHE_TTL = {
  dashboardSnapshot: 2 * 60,        // 2 minutes
  campaignList: 10 * 60,            // 10 minutes
  userRolePermissions: 5 * 60,      // 5 minutes
  contactSearchResults: 30,          // 30 seconds
};
```

### Background Job Scaling
```
Low volume:    Single worker process
Medium volume: 2–3 worker processes (separate from API)
High volume:   Dedicated worker instances with queue partitioning
               - sync-worker: handles Google Sheets sync
               - automation-worker: handles rule execution
               - notification-worker: handles notifications
```

## Frontend Scalability

### Handling Large Contact Lists
- Server-side pagination — never fetch all contacts to the frontend.
- Virtual scrolling for within-page row virtualization (react-window).
- Avoid rendering > 100 DOM rows simultaneously.

### Bundle Size at Scale (Many Features)
- Code splitting by route ensures new features don't increase initial load time.
- Lazy-import feature-specific libraries (e.g., chart library only for reports page).
- Monitor bundle size in CI: alert if main bundle exceeds 200KB gzipped.

## Scalability Red Flags

Patterns that will fail at scale:

```typescript
// ❌ Loads ALL contacts to memory for filtering
const contacts = await contactRepo.findAll(); // Will OOM at 1M contacts
const filtered = contacts.filter(c => c.status === 'NEW');

// ✅ Filters in database
const contacts = await contactRepo.findAll({ status: 'NEW', page: 1, perPage: 25 });

// ❌ N+1 query
const leads = await leadRepo.findAll();
for (const lead of leads) {
  lead.owner = await userRepo.findById(lead.ownerId); // N queries!
}

// ✅ JOIN in one query
const leads = await leadRepo.findAllWithOwner({ page, perPage });
```

## Performance Monitoring for Scale

Key metrics to alert on:
- API p95 latency > 500ms.
- Database connection pool saturation > 80%.
- Background job queue depth > 1000 (growing backlog).
- Cache miss rate > 30% (cache not helping).
- Error rate > 0.1% (5xx responses).

## Scalability Review Checklist

Before shipping any feature that touches data at scale:
- [ ] No unbounded queries.
- [ ] All query parameters have LIMIT applied.
- [ ] Relevant columns are indexed.
- [ ] No N+1 query pattern.
- [ ] Expensive aggregations are cached or pre-computed.
- [ ] The feature does not store state in the application process.
- [ ] Background jobs are idempotent (safe to retry/scale horizontally).
- [ ] File storage uses object storage (S3), not local filesystem.

## What NOT to Do

- Do NOT store shared state in the Node.js process (in-memory).
- Do NOT load all records to memory for sorting/filtering.
- Do NOT add database indexes blindly — profile first.
- Do NOT add caching without defining TTL and invalidation strategy.
- Do NOT prematurely partition tables — profile and decide based on actual growth.
