---
name: background-jobs-scheduler
description: >-
  Use this skill when designing or implementing background job processing,
  scheduled tasks, delayed job execution, job queues, retry policies, failed
  job handling, or preventing duplicate job execution. Activate when any
  feature requires work to happen outside of the HTTP request lifecycle,
  including email sending, data synchronization, automation rule execution,
  overdue task detection, or any periodic maintenance job.
---

# Background Jobs & Scheduler

You are acting as a Senior Backend Engineer specializing in reliable background
job processing. Your responsibility is to ensure all async work is durable,
observable, idempotent, and correctly retried on failure.

## Core Principles

1. **Background work must be durable** — survives server restarts.
2. **Every job must be idempotent** — re-running a job produces the same result.
3. **Every job must be observable** — status, errors, and retries are logged.
4. **Failed jobs must not be silently lost** — dead-letter queue or alerting.
5. **Duplicate jobs must be prevented** — use job deduplication keys.

## Recommended Stack

**Node.js/TypeScript**: BullMQ (Redis-backed) or pg-boss (PostgreSQL-backed).
- **BullMQ** — best for high-throughput, Redis availability required.
- **pg-boss** — best when Redis is not available; uses PostgreSQL for durability.

For a CRM workload (moderate throughput, high durability requirement):
- **pg-boss is preferred** — leverages existing PostgreSQL, no extra Redis dependency.

## Job Queue Structure

```typescript
// Queue definitions — one queue per domain
const queues = {
  'sync.google-sheets':     { concurrency: 1, priority: 1 },
  'automation.rule-engine': { concurrency: 5, priority: 2 },
  'notifications.send':     { concurrency: 10, priority: 3 },
  'tasks.overdue-check':    { concurrency: 1, priority: 2 },
  'audit.cleanup':          { concurrency: 1, priority: 5 },
};
```

## Job Definition Pattern

```typescript
// jobs/googleSheetsSyncJob.ts
export interface GoogleSheetsSyncJobData {
  spreadsheetId: string;
  triggeredBy: 'scheduler' | 'manual';
  adminId?: string;
}

export const GOOGLE_SHEETS_SYNC_JOB = 'sync.google-sheets';

// Singleton key prevents concurrent runs of the same job
export const googleSheetsSyncJobKey = (spreadsheetId: string) =>
  `${GOOGLE_SHEETS_SYNC_JOB}:${spreadsheetId}`;
```

## Worker Pattern

```typescript
// workers/googleSheetsSyncWorker.ts
export async function processGoogleSheetsSyncJob(
  job: Job<GoogleSheetsSyncJobData>
): Promise<void> {
  const { spreadsheetId, triggeredBy } = job.data;
  const logger = createJobLogger(job.id, GOOGLE_SHEETS_SYNC_JOB);

  logger.info('Starting Google Sheets sync', { spreadsheetId, triggeredBy });

  try {
    await googleSheetsSyncService.run(spreadsheetId);
    logger.info('Sync completed successfully');
  } catch (error) {
    logger.error('Sync failed', { error: error.message, stack: error.stack });
    throw error; // Re-throw to trigger retry
  }
}
```

## Retry Policy

Default retry configuration (adjust per job type):

```typescript
const defaultJobOptions = {
  attempts: 3,
  backoff: {
    type: 'exponential',
    delay: 5000, // 5s, 25s, 125s
  },
  removeOnComplete: { age: 24 * 3600, count: 100 },
  removeOnFail: false, // Keep failed jobs for inspection
};

// Critical jobs (sync, automation): more retries
const criticalJobOptions = {
  attempts: 5,
  backoff: { type: 'exponential', delay: 10000 },
};

// Notification jobs: fewer retries, faster backoff
const notificationJobOptions = {
  attempts: 2,
  backoff: { type: 'fixed', delay: 30000 },
};
```

## Idempotency

Every job must be designed to be safely re-runnable:

```typescript
// Use job deduplication key
await queue.add(
  GOOGLE_SHEETS_SYNC_JOB,
  jobData,
  {
    jobId: googleSheetsSyncJobKey(spreadsheetId), // Dedup key
    ...defaultJobOptions,
  }
);
// BullMQ: if a job with this ID already exists in pending state, the new one is discarded
```

## Scheduler (Recurring Jobs)

```typescript
// Scheduled jobs defined at application startup
const scheduledJobs = [
  {
    name: 'sync.google-sheets',
    cron: '*/15 * * * *',      // Every 15 minutes
    data: { spreadsheetId: config.GOOGLE_SHEETS_ID, triggeredBy: 'scheduler' },
    options: { jobId: 'google-sheets-sync-scheduled' }, // Prevents duplicate schedules
  },
  {
    name: 'tasks.overdue-check',
    cron: '*/5 * * * *',       // Every 5 minutes
    data: {},
    options: { jobId: 'overdue-task-check' },
  },
  {
    name: 'audit.cleanup',
    cron: '0 2 * * *',         // Daily at 2am UTC
    data: {},
    options: { jobId: 'audit-cleanup-daily' },
  },
];
```

## Dead-Letter Queue (DLQ)

Jobs that exhaust all retries move to the DLQ:

- Store failed jobs in a `failed_jobs` table (if using pg-boss) or BullMQ failed set.
- Alert (email/Slack) when a job fails after all retries.
- Admin can inspect failed jobs in the UI.
- Admin can replay failed jobs manually.
- Dead jobs older than 30 days are archived.

## Job Observability

Every job must log:
- Job ID.
- Queue name.
- Job type.
- Data summary (not full payload for large jobs).
- Start time, end time, duration.
- Retry attempt number.
- Success or failure + error details.

```typescript
function createJobLogger(jobId: string, jobType: string) {
  return logger.child({
    jobId,
    jobType,
    context: 'background-job',
  });
}
```

## Concurrency Control

- Google Sheets sync: `concurrency: 1` — only ONE sync at a time.
- Automation rule engine: `concurrency: 5` — can process 5 rules in parallel.
- Notifications: `concurrency: 10` — can send 10 notifications in parallel.
- Use `rate limiter` on queues that call external APIs (Google Sheets API quota).

## Job Monitoring Dashboard (Admin UI)

Surface for admin users:
- Active jobs (currently running).
- Waiting jobs (queued, not yet started).
- Completed jobs (last 24 hours).
- Failed jobs (with error details and retry button).
- Dead-letter jobs.
- Queue depths (jobs waiting per queue).

## Graceful Shutdown

```typescript
// On SIGTERM/SIGINT:
// 1. Stop accepting new jobs.
// 2. Wait for currently running jobs to complete (with timeout).
// 3. Close queue connections.
// 4. Exit.
process.on('SIGTERM', async () => {
  await worker.close(); // Waits for active jobs to complete
  await queue.close();
  process.exit(0);
});
```

## What NOT to Do

- Do NOT perform background work inside HTTP request handlers.
- Do NOT use `setInterval` or `setTimeout` for recurring jobs (not durable).
- Do NOT use in-memory queues in production (data lost on restart).
- Do NOT skip idempotency (risk of duplicate operations on retry).
- Do NOT silently swallow job errors without re-throwing.
- Do NOT run concurrent instances of singleton jobs (sync, cleanup).
- Do NOT remove failed jobs until they have been reviewed.
