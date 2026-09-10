# Gulf Leads Import & Reconciliation Guide

This document describes the Gulf Leads import pipeline, deduplication logic, salesperson mapping, Excel upload API, and production migration procedure for the Alpha Pro MENA CRM.

---

## 1. Overview & Architecture

The import pipeline reconciles data between external workbooks (such as `Gulf Leads (1).xlsx`) or live Google Sheets and the CRM's internal database.

Key architectural characteristics:
- **Zero Duplication**: Deduplication across sheets (such as `Sheet16` and `Leads`) and against the existing database is performed via SHA-256 `import_key` hashes and corroborated phone/email matching.
- **In-Place Updates**: Existing contacts are never recreated. Their existing IDs, call logs, activity notes, and assigned owners are preserved. Blank fields are enriched without overwriting existing data.
- **Do Not Call (DNC) Guarantee**: Contacts flagged as `is_dnc` are strictly protected and never modified by automated imports.
- **Company Deduplication & Normalization**: Companies are looked up case-insensitively (`ilike`) before insertion. Existing companies are reused.
- **No Self-Assignment**: Operators importing files (such as Aseel) are never automatically assigned as contact owners. Ownership is resolved strictly from the salesperson column in the source data.

---

## 2. Source Worksheet Mappings

The authoritative workbook `Gulf Leads (1).xlsx` contains several worksheets with distinct purposes and structures:

| Worksheet | Header Row | Column Layout / Purpose | Handling |
|---|---|---|---|
| **Leads** | Row 1 (header) | A: Name, B: Company, C: Position, D: Phone, E: Email, F: Salesperson, G–I: Call attempts 1–3 | Primary contact source (~4,390 named contacts) |
| **Sheet16** | **None** (Row 1 is data) | A: Name, B/C: Position or Company, D: Phone, E: Email, F: Salesperson | Row 1 (`Ayman Ali`) is imported. Column B/C ambiguity is dynamically resolved using the Companies reference set. Overlaps with Leads are merged by `import_key`. |
| **Companies** | Row 1 (header) | Reference list of verified company names | Used as an in-memory lookup set to disambiguate B/C columns; skipped as contact source. |
| **Demo** | Row 1 (header) | Subset of leads with demo tracking | Merged into contacts, propagates `DEMO_SCHEDULED` status hint. |
| **Qusai** | Row 1 (header) | Salesperson subset | Merged into contacts, assigned to Qusai. |
| **Ghaida fu** / **Amin fu** | Row 1 (header) | Follow-up tracking subsets | Merged into contacts, preserves follow-up notes. |
| **Oman** / **Oman Leads** / **Oman L.S** / **Oman Amin** | Varies | Oman country subsets | Normalized using `OM` country hint (+968 dial code). |

### Special Row Rules in Sheet16
- **Row 67**: Missing contact name in Column A (contains activity logs only). Filtered out as invalid and logged in the import error report.
- **Rows 693–698 (SHAWARMER)**: Column B is the company name (`SHAWARMER`) and Column C is the position. Column F (Salesperson) is blank. Contacts are imported with `UNASSIGNED` status and `owner_id = NULL`.

---

## 3. Salesperson-to-CRM User Map

Salesperson names in the workbook are mapped to real CRM user accounts as follows:

| Source Sheet Value | CRM User Email | Role | Notes |
|---|---|---|---|
| `Saleh` | `saleh@alphapromena.com` | SALES_USER | Primary sales agent |
| `Hassan` | `hassan@alphapromena.com` | SALES_USER | Primary sales agent |
| `Amin` | `amin@alphapromena.com` | SALES_USER | Primary sales agent |
| `Ghaida` / `Ghayda` | `ghaida@alphapromena.com` | SALES_USER | Primary sales agent |
| `Qusai` | `qusai@alphapromena.com` | SALES_USER | Primary sales agent |
| `Maria` | *(None)* | **UNASSIGNED** | Former employee; imported with `owner_id = NULL` and logged in `awaiting_review` |
| `Raneem` | *(None)* | **UNASSIGNED** | Former employee; imported with `owner_id = NULL` and logged in `awaiting_review` |
| *(Empty)* | *(None)* | **UNASSIGNED** | Imported with `status = UNASSIGNED` |
| `Aseel` | `aseel@alphapromena.com` | DATA_OPS | **Never assigned as owner** (operator role) |

---

## 4. CLI Importer Usage

Run the import script from the `backend/` directory:

### Dry Run (Preview counts, no DB writes)
```bash
python -m scripts.import_leads --dry-run
```

### Full Import
```bash
python -m scripts.import_leads
```

### Import a Single Worksheet
```bash
python -m scripts.import_leads --sheet Leads
python -m scripts.import_leads --sheet Sheet16
```

### Import Custom File
```bash
python -m scripts.import_leads --file "/path/to/workbook.xlsx"
```

---

## 5. Web API Endpoint (Excel Upload)

Authorized users (`DATA_OPS` or above) can upload workbooks via the REST API:

- **Endpoint**: `POST /api/v1/integrations/excel-import`
- **Authentication**: Bearer token (`Authorization: Bearer <jwt>`)
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file` (File, required): `.xlsx` file (max 50 MB)
  - `sheet_name` (string, optional): Specific sheet to process (default: all configured sheets)
  - `dry_run` (boolean, optional): If `true`, returns report without modifying database

### Response Structure
```json
{
  "message": "Import completed.",
  "dry_run": false,
  "uploaded_by": "018f...",
  "sheets_processed": [
    {"sheet": "Leads", "rows": 4390},
    {"sheet": "Sheet16", "rows": 2077}
  ],
  "report": {
    "summary": {
      "total_rows_read": 6467,
      "total_invalid": 1,
      "total_intra_duplicates": 2077,
      "total_db_matched": 7,
      "total_new": 4382,
      "total_awaiting_review": 11,
      "total_inserted": 4382,
      "total_updated": 7,
      "total_skipped": 0,
      "total_errors": 0,
      "total_conflicts": 0
    },
    "per_sheet": { ... },
    "awaiting_review_rows": [ ... ],
    "invalid_rows": [ ... ],
    "conflict_rows": [ ... ]
  }
}
```

---

## 6. Live Google Sheets Integration

The Google Sheets sync service (`app/integrations/google_sheets/service.py`) shares the same `app.imports` reconciliation library.

### Configuration
To enable live Google Sheets synchronization, provide service account credentials in `backend/.env`:
```ini
GOOGLE_SERVICE_ACCOUNT_EMAIL="your-service-account@project.iam.gserviceaccount.com"
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
```
The spreadsheet must be shared with `GOOGLE_SERVICE_ACCOUNT_EMAIL` with Viewer or Editor permissions. It does **not** need to be made public.

---

## 7. Production Migration & Verification Checklist

When deploying this branch to staging/production:

1. **Verify Database Backup**: Ensure a snapshot or `pg_dump` backup of PostgreSQL exists.
2. **Deploy Code**: Merge branch and run database migrations:
   ```bash
   alembic upgrade head
   ```
3. **Execute Dry Run**:
   ```bash
   python -m scripts.import_leads --dry-run
   ```
   Inspect the output: confirm `total_inserted`, `total_matched`, and verify that `total_errors` is 0.
4. **Execute Import**:
   ```bash
   python -m scripts.import_leads
   ```
5. **Verify Idempotency**:
   ```bash
   python -m scripts.import_leads
   ```
   Must output `0 inserted` on the second run.
6. **Review Awaiting Review Queue**:
   Review contacts formerly owned by Maria and Raneem in the CRM Admin dashboard and reassign them as appropriate.
