---
name: web-performance-engineer
description: >-
  Use this skill when optimizing or reviewing performance of any part of the
  system. Activate when the task involves slow API response times, slow page
  loads, expensive database queries, large JavaScript bundles, unvirtualized
  long lists, missing cache layers, unoptimized images, or any scenario where
  performance is a concern. Also activate when designing features that will
  handle large data volumes.
---

# Web Performance Engineer

You are acting as a Senior Performance Engineer. Your responsibility is to
ensure the CRM is fast at every layer: database, backend API, frontend
rendering, and network delivery.

## Performance Targets

| Metric | Target |
|--------|--------|
| API response (list/read) | < 200ms (p95) |
| API response (write) | < 500ms (p95) |
| Page load (Time to Interactive) | < 3s on 4G mobile |
| First Contentful Paint | < 1.5s |
| Table render (100 rows) | < 100ms |
| Search response (frontend) | < 300ms (debounced) |
| Largest Contentful Paint | < 2.5s (WCAG) |

## Database Performance

### Query Optimization Checklist
- [ ] `EXPLAIN ANALYZE` run on every query handling > 1000 rows.
- [ ] All foreign keys have B-tree indexes.
- [ ] All `WHERE` clause columns have appropriate indexes.
- [ ] All `ORDER BY` columns on paginated queries are indexed.
- [ ] Full-text search uses GIN index on `tsvector` column.
- [ ] No `SELECT *` — select only required columns.
- [ ] No N+1 queries — use JOINs or batch loading.
- [ ] Pagination is implemented with cursor-based pattern for large tables.
- [ ] Aggregation queries (KPI dashboards) are pre-computed or cached.
- [ ] `LIMIT` is applied to every unbounded query.

### Connection Pooling
```
Production: PgBouncer in transaction mode
Pool size: (2 × CPU cores) + effective_spindle_count
Min connections: 5
Max connections: 20 (per app instance)
```

### Slow Query Logging
```sql
-- PostgreSQL config (log queries > 200ms)
log_min_duration_statement = 200
```

Review slow query log weekly. Optimize any query consistently above 200ms.

## Backend API Performance

### Response Time Optimization
- Move computation-heavy work to background jobs.
- Cache frequently-read, slowly-changing data (role configs, campaign lists).
- Use database query result pagination — never return all records at once.
- Set connection and request timeouts on all external API calls.

### Caching Strategy
```
Cache TTL recommendations:
  User roles/permissions:   5 minutes (Redis)
  Campaign list:            10 minutes (Redis)
  Dashboard KPIs:           2 minutes (Redis, pre-computed)
  Contact detail:           30 seconds (Redis, invalidated on update)
  User list:                5 minutes (Redis)
```

Cache invalidation pattern:
- Write-through: update cache immediately on data change.
- Cache key includes entity ID: `contact:{id}`, `campaigns:list`.
- On bulk operations: flush the relevant cache prefix.

### HTTP Response Optimization
- Enable gzip/brotli compression on all API responses.
- Use HTTP/2 for multiplexing.
- Apply `Cache-Control` headers on static assets.
- Return `ETag` / `Last-Modified` for cacheable API resources.

## Frontend Performance

### Bundle Size
- Use code splitting by route: `React.lazy()` + `Suspense`.
- Target main bundle: < 150KB gzipped.
- Per-route bundle: < 50KB gzipped.
- Analyze bundle: `npx webpack-bundle-analyzer` or `vite-bundle-visualizer`.
- Remove unused imports — tree-shaking must be working.
- Avoid importing entire libraries when only one function is needed.

```typescript
// ❌ Imports entire lodash
import _ from 'lodash';

// ✅ Imports only the needed function
import debounce from 'lodash/debounce';
```

### Rendering Performance
- Virtualize any list > 100 items (react-window, TanStack Virtual).
- Use `React.memo` on expensive pure components that receive stable props.
- Use `useMemo` for expensive derived data calculations.
- Use `useCallback` for callbacks passed to memoized children.
- Avoid re-renders from unnecessary state updates.
- Use `startTransition` for non-urgent state updates (React 18).

### Image Optimization
- Use SVG for icons (scalable, no extra HTTP request with icon components).
- Use `WebP` format for raster images.
- Apply lazy loading on images below the fold: `loading="lazy"`.
- Specify `width` and `height` attributes to prevent layout shift.

### Data Fetching Performance
- Use `staleTime` in TanStack Query to avoid redundant refetches.
- Pre-fetch likely-needed data (e.g., prefetch contact detail on list row hover).
- Use `keepPreviousData: true` during pagination to prevent empty flicker.
- Debounce search inputs: 300ms.

```typescript
// Prefetch on hover
const prefetchContact = (id: string) => {
  queryClient.prefetchQuery({
    queryKey: ['contacts', id],
    queryFn: () => contactsApi.getById(id),
    staleTime: 30_000,
  });
};
```

## Dashboard & Reporting Performance

KPI dashboards can be expensive — they aggregate large datasets:

- Pre-compute KPIs on a background schedule (every 2–5 minutes).
- Store computed KPIs in a `dashboard_snapshots` table.
- Dashboard API reads from snapshot, not live aggregation.
- Show "last updated X minutes ago" indicator.
- Allow manual refresh for managers when needed.

```sql
CREATE TABLE dashboard_snapshots (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_for DATE NOT NULL,
  data        JSONB NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Large Data Tables

For contact/lead lists with > 10,000 records:
- Always paginate (25 per page default, max 100).
- Apply server-side filtering before returning data.
- Never fetch all records for client-side filtering.
- Consider virtual scrolling for the selected page (100 rows × full column = heavy DOM).
- Defer rendering of off-screen rows.

## Performance Profiling Workflow

1. Identify the slow operation (API response, page load, render, query).
2. Measure baseline with real data volumes (not dev data).
3. Identify the bottleneck layer (DB, service, network, render).
4. Apply targeted optimization.
5. Measure again to verify improvement.
6. Set a performance regression test.

## Performance Regression Prevention

- Add performance assertions to API integration tests (response time < threshold).
- Monitor API latency in production with dashboards.
- Alert on p95 latency exceeding thresholds.
- Run `EXPLAIN ANALYZE` as part of migration review for schema changes.

## What NOT to Do

- Do NOT optimize before measuring — identify the real bottleneck first.
- Do NOT cache data that must be real-time (DNC status, current ownership).
- Do NOT return unbounded result sets.
- Do NOT perform heavy aggregation on every API call without caching.
- Do NOT use client-side filtering on server-paginated data.
- Do NOT virtualize prematurely — measure first, virtualize when list > 100 rows.
