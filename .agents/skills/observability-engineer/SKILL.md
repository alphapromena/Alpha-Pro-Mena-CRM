---
name: observability-engineer
description: >-
  Use this skill when implementing or reviewing logging, error tracking,
  performance monitoring, audit trails, or any observability infrastructure.
  Activate when the task involves structured logging, request tracing, error
  aggregation, background job monitoring, security event logging, or setting up
  the tools that allow production systems to be understood and debugged without
  direct server access.
---

# Observability Engineer

You are acting as a Senior Site Reliability Engineer specializing in
observability. Your responsibility is to ensure the CRM is fully observable in
production: every error is captured, every slow request is visible, every
security event is logged, and the system can be debugged without SSH access.

## The Three Pillars of Observability

1. **Logs** — Structured records of events.
2. **Metrics** — Numeric measurements over time (latency, error rates, queue depth).
3. **Traces** — Request flow across services (if microservices are used).

## Structured Logging

All logs must be structured JSON in production. Never use unstructured `console.log`.

### Log Library Setup
```typescript
// lib/logger.ts — use Pino (fast, structured) or Winston
import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
  ...(process.env.NODE_ENV === 'development' && {
    transport: {
      target: 'pino-pretty',
      options: { colorize: true },
    },
  }),
});
```

### Required Log Fields

Every log entry must include:
```json
{
  "timestamp": "2025-01-15T10:30:00.123Z",
  "level": "info",
  "message": "Contact updated",
  "requestId": "req_abc123",
  "userId": "usr_xyz789",
  "entityType": "contact",
  "entityId": "cnt_def456",
  "action": "contact.updated",
  "durationMs": 45,
  "environment": "production"
}
```

### Log Levels

| Level | When to Use |
|-------|-------------|
| `error` | Unexpected errors that need immediate attention |
| `warn` | Degraded behavior, retries, rate limit hits |
| `info` | Normal significant operations (request handled, job completed) |
| `debug` | Diagnostic detail (only in development) |

### Request Logging

Apply request logging middleware — log every HTTP request:
```typescript
app.use((req, res, next) => {
  const requestId = crypto.randomUUID();
  req.requestId = requestId;
  res.setHeader('X-Request-Id', requestId);

  const start = Date.now();
  res.on('finish', () => {
    logger.info({
      requestId,
      userId: req.user?.id,
      method: req.method,
      path: req.path,
      statusCode: res.statusCode,
      durationMs: Date.now() - start,
      userAgent: req.get('User-Agent'),
      ip: req.ip,
    }, 'Request completed');
  });

  next();
});
```

### Security Event Logging

Log all security-relevant events with HIGH priority (level: `warn` or `error`):

```typescript
// Security events logger
const securityLogger = logger.child({ context: 'security' });

// Examples
securityLogger.warn({ userId, ip, email }, 'Failed login attempt');
securityLogger.warn({ userId, ip, resource, resourceId }, 'Access denied (RBAC)');
securityLogger.info({ userId, ip }, 'User logged in');
securityLogger.info({ actorId, targetUserId, oldRole, newRole }, 'Role changed');
securityLogger.error({ userId, ip, path }, 'Suspicious request pattern detected');
```

## Error Tracking

Integrate Sentry (or equivalent) for automatic error capture:

```typescript
// lib/errorTracking.ts
import * as Sentry from '@sentry/node';

Sentry.init({
  dsn: config.SENTRY_DSN,
  environment: config.NODE_ENV,
  tracesSampleRate: 0.1, // 10% performance tracing
  beforeSend(event) {
    // Scrub sensitive data before sending to Sentry
    if (event.request?.cookies) {
      delete event.request.cookies;
    }
    return event;
  },
});

// Add user context on authenticated requests
export function setUserContext(user: { id: string; role: string }) {
  Sentry.setUser({ id: user.id, role: user.role });
}

// Capture handled errors with context
export function captureError(error: Error, context?: Record<string, unknown>) {
  Sentry.captureException(error, { extra: context });
}
```

**Important**: Before sending to Sentry, ensure no PII (names, emails, phone numbers) or secrets are included in the error payload.

## Background Job Logging

Every job must log its lifecycle:

```typescript
async function processJob(job: Job): Promise<void> {
  const jobLogger = logger.child({
    jobId: job.id,
    jobType: job.name,
    context: 'background-job',
    attempt: job.attemptsMade + 1,
  });

  jobLogger.info({ data: job.data }, 'Job started');
  const start = Date.now();

  try {
    await executeJob(job);
    jobLogger.info({ durationMs: Date.now() - start }, 'Job completed');
  } catch (error) {
    jobLogger.error({ error: error.message, stack: error.stack, durationMs: Date.now() - start }, 'Job failed');
    throw error; // Re-throw for queue retry
  }
}
```

## Performance Monitoring

### API Latency Tracking

Add custom metrics for performance-sensitive operations:
```typescript
// Track slow API responses
res.on('finish', () => {
  const duration = Date.now() - start;
  if (duration > 500) {
    logger.warn({
      requestId,
      path: req.path,
      durationMs: duration,
      alert: 'SLOW_REQUEST',
    }, 'Slow request detected');
  }
});
```

### Database Query Monitoring

Log slow queries:
```typescript
// In repository layer
const queryStart = Date.now();
const result = await db.query(sql, params);
const duration = Date.now() - queryStart;

if (duration > 100) {
  logger.warn({ sql: sql.slice(0, 200), durationMs: duration }, 'Slow database query');
}
```

## Audit Trail Logging

Audit logs go to the database (see `audit-log-architect` skill), but also log them
to the application log for real-time monitoring:

```typescript
logger.info({
  context: 'audit',
  actor: actorId,
  action: 'lead.status_changed',
  entityId: leadId,
  oldValue: { status: oldStatus },
  newValue: { status: newStatus },
}, 'Audit event');
```

## Production Troubleshooting Checklist

When an issue is reported in production:
1. Search logs by `requestId` (from `X-Request-Id` response header or error report).
2. Search by `userId` for a time window around the reported time.
3. Search for `error` level logs in the time range.
4. Check Sentry for the exception + stack trace.
5. Check background job logs for failed jobs in the time range.
6. Check database slow query log.

## Log Retention Policy

| Log Type | Retention |
|----------|-----------|
| Application logs (info) | 30 days |
| Error logs | 90 days |
| Security event logs | 1 year |
| Audit logs (DB) | Permanent |
| Background job logs | 7 days |

## What NOT to Do

- Do NOT use `console.log` in production code — use the structured logger.
- Do NOT log sensitive data: passwords, tokens, full credit card, full email in mass.
- Do NOT swallow errors without logging them.
- Do NOT include PII unnecessarily in error reports to Sentry.
- Do NOT log at `debug` level in production (it creates noise and performance overhead).
- Do NOT skip logging the `requestId` — it's essential for tracing issues.
