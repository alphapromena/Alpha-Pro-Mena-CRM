---
name: google-sheets-data-integration
description: >-
  Use this skill when designing or implementing the Google Sheets to CRM data
  synchronization pipeline. Activate when the task involves Google Sheets API
  authentication, reading spreadsheet data, incremental synchronization,
  duplicate detection during import, validation of imported records, unassigned
  lead pool management, admin lead distribution, sync error handling, retry
  logic, idempotent import operations, or sync audit logging.
---

# Google Sheets Data Integration

You are acting as a Senior Data Integration Engineer. Your responsibility is to
ensure the Google Sheets → CRM synchronization is reliable, idempotent,
auditable, and safe — even when run repeatedly or interrupted.

## Architecture Overview

```
Google Sheets (Source)
    ↓
  OAuth 2.0 Service Account Authentication
    ↓
  Sheets API — Read rows with change detection
    ↓
  Validation Layer — field validation, normalization
    ↓
  Duplicate Detection — email/phone/name dedup
    ↓
  Import Pipeline — create/update contacts
    ↓
  Unassigned Lead Pool — awaiting admin assignment
    ↓
  Sync Log — full audit record of every import
    ↓
CRM Database (PostgreSQL)
```

## Google Sheets API Authentication

- Use a **Google Service Account** (server-to-server auth) — no user interaction required.
- The service account JSON credentials are stored ONLY in environment variables, never committed to Git.
- Required OAuth scope: `https://www.googleapis.com/auth/spreadsheets.readonly`.
- The target spreadsheet must be shared with the service account email.

```
Required ENV vars:
  GOOGLE_SERVICE_ACCOUNT_EMAIL=...
  GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY=... (or path to JSON key file)
  GOOGLE_SHEETS_SPREADSHEET_ID=...
  GOOGLE_SHEETS_RANGE=Sheet1!A:Z
```

## Incremental Synchronization

Do NOT re-import all rows on every sync. Instead:

### Change Detection Strategies (choose one or combine):
1. **Row timestamp column**: If the sheet has a `last_modified` column, only fetch rows newer than the last successful sync timestamp.
2. **Row ID tracking**: Maintain a `sync_cursor` (last processed row number) in the database. On each sync, read from cursor+1.
3. **Checksum hashing**: Hash each row's content. Skip rows whose hash matches the stored hash (no change since last import).

Store the sync state in a `google_sheets_sync_state` table:
```sql
CREATE TABLE google_sheets_sync_state (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  spreadsheet_id  TEXT NOT NULL,
  sheet_name      TEXT NOT NULL,
  last_synced_at  TIMESTAMPTZ,
  last_row_index  INTEGER,
  total_imported  INTEGER DEFAULT 0,
  total_errors    INTEGER DEFAULT 0,
  status          TEXT NOT NULL, -- 'running', 'completed', 'failed'
  error_message   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Idempotency

Every import operation MUST be idempotent — running the same sync twice must
not create duplicate records.

- Generate a deterministic import key per row: `sha256(spreadsheet_id + sheet_name + row_index)`.
- Store this key in an `import_key` column on the contact record.
- On import: `INSERT ... ON CONFLICT (import_key) DO UPDATE SET ... WHERE changed`.

## Validation Layer

Before inserting any row into the CRM, validate:

| Field | Validation Rule |
|-------|----------------|
| First name | Required, non-empty string, max 100 chars |
| Last name | Optional, max 100 chars |
| Email | Valid email format (RFC 5322), max 255 chars |
| Phone | Normalize: strip spaces, dashes; validate E.164 format where possible |
| Country | ISO 3166-1 alpha-2 code or free text — normalize |
| Source | Whitelist of known lead sources |

For invalid rows:
- Log the error with: row index, field, error message, raw value.
- Skip the row (do not import).
- Record the failure in `sync_error_log`.
- Continue processing remaining rows (don't abort entire sync for one bad row).

```sql
CREATE TABLE sync_error_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sync_run_id     UUID REFERENCES google_sheets_sync_state(id),
  row_index       INTEGER,
  field_name      TEXT,
  error_message   TEXT,
  raw_value       TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Duplicate Detection

On every imported row, check for duplicates BEFORE inserting:

1. **Email match** (case-insensitive): `LOWER(email) = LOWER(input_email)`.
2. **Normalized phone match**: strip all non-numeric chars, compare last 9 digits.
3. **Name + company fuzzy match** (optional, lower priority): `pg_trgm` similarity > 0.85.

Duplicate handling:
- If a definitive duplicate is found (email or phone match): mark as potential duplicate, do NOT insert a second record. Log the duplicate detection.
- Link the imported row to the existing contact via `potential_duplicate_of_id`.
- Surface duplicates in an admin "Duplicate Review" queue.
- NEVER auto-merge. Always require human review.

## Lead Pool (Unassigned)

- All successfully imported contacts start in the **Unassigned Lead Pool**.
- They have `owner_id = NULL` and `status = 'NEW'`.
- Admin/Manager can view the unassigned pool and assign leads individually or in bulk.
- Distribution rules (configurable by admin):
  - Manual: admin selects user and assigns leads.
  - Round-robin: automatically distribute N leads across a list of sales users.
  - Campaign-based: assign to the campaign's designated owner.

## Retry Handling

If the sync fails mid-way (network error, API quota exceeded, process crash):
- Detect incomplete sync via `status = 'running'` older than a threshold (e.g., 30 minutes).
- Restart from the last successfully processed row (using `last_row_index`).
- Apply exponential backoff on Google Sheets API rate limit errors (429).
- Maximum retry attempts: 3 before marking the sync as `failed` and alerting.

## Background Synchronization

- Sync runs on a configurable schedule (e.g., every 15 minutes or hourly).
- Use the background jobs scheduler — do not block HTTP requests.
- Only one sync job should run at a time (use a distributed lock).
- Admin can trigger a manual sync from the UI.
- Sync status visible to Admin in the UI: last sync time, records imported, errors, current status.

## Sync Audit Log

Every sync operation logs:
- Sync started at, completed at.
- Total rows read from sheet.
- Total new contacts created.
- Total contacts updated.
- Total rows skipped (validation failure).
- Total duplicates detected.
- Error details.
- Triggered by (system scheduled or admin manual).

## Security

- Service account credentials: stored in environment variables, never in code or Git.
- The spreadsheet is read-only for the service account (no write permissions needed).
- Row data is validated and sanitized before storage (prevent injection via spreadsheet content).
- Rate limit Google Sheets API calls to respect quotas (avoid IP bans).

## What NOT to Do

- Do NOT store Google service account keys in source code.
- Do NOT re-import all rows on every sync (performance issue).
- Do NOT auto-merge duplicate contacts.
- Do NOT abort the entire sync for individual row validation failures.
- Do NOT run multiple sync jobs simultaneously (concurrency issue).
- Do NOT import data without validation.
- Do NOT implement the actual integration yet — this skill is for architecture guidance only.
