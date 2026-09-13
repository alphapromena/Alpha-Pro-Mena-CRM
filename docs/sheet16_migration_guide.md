# Sheet16 Authoritative Data Replacement & Migration Guide

## Overview
This document outlines the authoritative replacement of the Alpha Pro MENA CRM active leads/contacts dataset using `CRM data.xlsx`.

## 1. Source-of-Truth Architecture

### Active Contacts: `Sheet16`
- **Only Active Source**: The worksheet named strictly `Sheet16` is used for active contact/lead numbers and contact information.
- **Row 1 Preservation**: Row 1 contains valid contact data (`Ayman Ali`, Data Governance Manager, STC Bank, `+966 59 439 0699`) and is preserved.
- **Row 67 Exclusion**: Row 67 is an empty placeholder row (`[None, None, None, None, None, 'Saleh', 'skip', ...]`) and is excluded.
- **Valid Contact Rows**: 2,077 rows.
- **Unique Canonical Contacts**: 2,055 unique records (after deduplication by normalized phone/email/identity).
- **Per-Salesperson Breakdown**:
  - **Amin**: 675 rows / 671 unique canonical contacts
  - **Ghaida**: 493 rows / 490 unique canonical contacts
  - **Saleh**: 458 rows / 445 unique canonical contacts
  - **Hassan**: 445 rows / 443 unique canonical contacts
  - **Unassigned**: 6 rows / 6 unique canonical contacts

### Master Companies: `Companies`
- **Master Enterprise Directory**: 4,041 total rows scanned -> 3,699 clean canonical enterprise companies.
- Standardized Arabic/English company titles with deduplication and whitespace stripping.
- All Sheet16 contacts are linked directly to these canonical company records.

### Archiving: `Leads` Worksheet
- **Archive Only**: 4,392 rows from the `Leads` worksheet are preserved in the `leads_archive` database table.
- **Audit Columns**: `id`, `batch_id`, `sheet_name`, `row_number`, `raw_data` (JSON), `name`, `company_name`, `position`, `phone`, `email`, `salesperson`, `row_checksum`, `archived_at`.
- **Zero active contacts** are sourced from the `Leads` sheet.

### Historical Activities: `Demo` and Follow-up Sheets
- **112 Demos** extracted and linked with meeting outcomes, dates, and salesperson assignment.
- **251 Follow-ups** extracted from `Ghaida fu`, `Amin fu`, and `Sheet16` next-step columns.

---

## 2. Database Schema Migrations

The database migration is handled automatically via `app.core.auto_migrate.run_migrations_now(session)`:
- Added `leads_archive` table with indexes on `batch_id`, `phone`, `email`, and `salesperson`.
- Added `company_id`, `next_step`, `source_sheet`, and `source_row` columns to `follow_ups`.
- Added `source_sheet` and `source_row` columns to `demos`.

---

## 3. How to Run the Migration

### Dry-Run Mode (Safe Preview)
```bash
python backend/scripts/replace_active_leads_from_sheet16.py --file "CRM data.xlsx" --dry-run
```

### Live Execution (Local SQLite or Neon PostgreSQL)
Set `DATABASE_URL` to your target database and run:
```bash
python backend/scripts/replace_active_leads_from_sheet16.py --file "CRM data.xlsx"
```
The script is 100% idempotent: running it multiple times produces zero duplicates.
