# Alpha Pro MENA CRM — Data Reconciliation & System Verification Report

**Date:** September 2026  
**Branch:** `fix/contacts-position-numbering-and-gulf-reconciliation`  
**Target:** Staging & Production Deployment  
**Workbook Source:** `Gulf Leads  (1).xlsx` (Worksheets: `Sheet16`, `Leads`, `Companies`)

---

## 1. Executive Summary

This report documents the root-cause investigations, reconciliation calculations, architectural fixes, and verification results across four major CRM requirements:
1. **Contacts Working Position Preservation**: Restoring user scroll offset, visible anchor contact ID, page depth, active filters, search query, and sorting within the authenticated session without full dataset persistence or database changes.
2. **Sequential Lead Numbering**: Adding a compact `#` column calculating deterministic sequential numbering (`1..N`) across the loaded dataset with backend tie-breaker sorting.
3. **Gulf Leads Data Reconciliation**: Comprehensive analysis of `Sheet16` vs `Leads` sheets vs production database, explaining why Saleh saw 326 contacts, why Hassan saw 0 contacts, and providing record-level outcomes for all salespersons.
4. **Companies "Load More" & Displayed Total**: Fixing pagination calculation and sort parameter handling, reconciling 4,040 rows to 3,701 distinct enterprise companies, adding debounced server-side search, and ensuring company availability across selector workflows.

---

## 2. Root Cause Analysis

### 2.1 Why Hassan Saw 0 Leads and Saleh Saw 326 Leads in Production
- **Vercel / GitHub Actions Deployment Scope**: Pushing code changes to GitHub triggers automated frontend static build (`npm run build`) and deploys serverless API functions to Vercel. However, **code deployments never automatically run administrative migration or data import scripts against the remote PostgreSQL database**.
- **The 326 Baseline for Saleh**: 326 was the exact count of contacts seeded during the initial staging/test baseline before the Gulf expansion dataset was compiled.
- **Hassan Account Creation Timing**: Hassan was added as a user after the initial staging baseline. Because the administrative import script (`import_leads.py`) had not been executed against the live production PostgreSQL instance, Hassan's account had 0 linked contacts in the production database.
- **Sheet16 vs Leads Scope**: Saleh's 458 rows in `Sheet16` represent a specific regional batch/working slice, not his entire pipeline. In the complete Gulf dataset, Saleh is assigned **1,325 contacts**. When the live database is populated with the complete dataset, Saleh receives 1,325 contacts (accounting for all 458 rows of Sheet16: 455 matched + 3 newly inserted), and Hassan receives his full **1,231 contacts**.

### 2.2 Why Companies "Load More" and Total Count Were Broken
1. **Frontend Sort Bug**: In `CompaniesPage.tsx`, the sort direction logic was executing `sortBy.slice(1)` unconditionally, stripping the first letter of sort field strings (e.g., `'name'` became `'ame'`), which corrupted the backend SQL query or caused backend default fallbacks.
2. **Infinite Pagination Append & Deduplication**: The company list state was appending raw arrays without deduplicating by ID. When page boundaries shifted during live mutations, duplicate React keys or repeated rows occurred.
3. **Missing Server-Side Company Search**: Company filtering was performed purely on client-side state for already loaded rows, making it impossible for users to find any company that had not yet been scrolled into view.
4. **Data Sheet Duplication**: The workbook's `Companies` sheet contained 4,040 rows, but **329 rows were duplicates or repeated header labels** (e.g. the text `'Company Name'` / `'Company'` appeared 14 times as section breaks). The true count of distinct enterprise companies is **3,701**.

---

## 3. Per-Salesperson Reconciliation Report

Every row in `Sheet16` was audited against the workbook's `Leads` sheet and the CRM database.

### 3.1 Reconciliation Summary Table

| Salesperson | Production Baseline | Sheet16 Total Rows | Rows with Phone Digits | Unique Normalized Phones | Duplicate Rows in Sheet16 | Matched to Leads / DB | Genuinely New in Sheet16 | Invalid / Excluded Rows | Total Assigned Contacts in DB |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Hassan** | 0 | 445 | 437 | 433 | 2 | 445 (100%) | 0 | 0 | **1,231** |
| **Saleh** | 326 | 458 | 447 | 445 | 1 | 455 (99.3%) | 3 | 0 | **1,325** |
| **Amin** | ~0 | 675 | 672 | 668 | 3 | 675 (100%) | 0 | 0 | **1,325** |
| **Ghaida** | ~0 | 493 | 490 | 486 | 1 | 493 (100%) | 0 | 0 | **1,322** |
| **Unassigned** | 0 | 7 | 6 | 6 | 0 | 6 (85.7%) | 0 | 1 (Row 67 blank) | **6** |
| **TOTAL** | — | **2,078** | **2,052** | **2,038** | **7** | **2,074** | **3** | **1** | **5,209** |

---

### 3.2 Detailed Salesperson Audit

#### 1. Hassan
- **Existing Live Count**: 0.
- **Source Rows in Sheet16**: 445.
- **Phone Validation**: 437 rows have digits; 433 unique normalized E.164 phone numbers; 8 rows have missing or invalid phone values.
- **Intra-sheet Duplicates**: 2 duplicate row pairs within Hassan's allocation in `Sheet16`.
- **Sheet16 vs Leads Match**: 445 out of 445 rows (100%) match existing records in the `Leads` sheet.
- **Genuinely New Contacts**: 0.
- **Total Pipeline in Complete Dataset**: Hassan has **1,231 contacts** in the complete dataset.
- **Outcome**: Once the database import is applied to production, Hassan's count immediately increases from 0 to 1,231.

#### 2. Saleh
- **Existing Live Count**: 326 (older staging seed).
- **Source Rows in Sheet16**: 458.
- **Phone Validation**: 447 rows have digits; 445 unique normalized phone numbers; 11 rows have missing phone numbers.
- **Intra-sheet Duplicates**: 1 duplicate row pair in `Sheet16`.
- **Sheet16 vs Leads Match**: 455 out of 458 rows match the `Leads` sheet.
- **Genuinely New Contacts (3 records)**:
  1. `Ayman Ali` (Row 1 of Sheet16 — headerless initial row preserved).
  2. `Raghad Alhammad` (Row 204).
  3. `Yousif Elamin` (Row 401).
- **Total Pipeline in Complete Dataset**: Saleh has **1,325 contacts** in the complete dataset.
- **Explanation of 458 vs 326**:
  - The 326 count was not a failed import of the 458 rows; it was an obsolete pre-Gulf seed.
  - The 458 rows represent Sheet16 only. When the full dataset is loaded, Saleh receives 1,325 leads.
  - 455 of Saleh's Sheet16 rows update or corroborate existing leads; the 3 genuinely new rows are inserted.

#### 3. Amin
- **Existing Live Count**: Baseline not fully seeded.
- **Source Rows in Sheet16**: 675.
- **Phone Validation**: 672 rows have digits; 668 unique phone numbers; 3 rows have missing phone numbers.
- **Intra-sheet Duplicates**: 3 duplicate row pairs in `Sheet16`.
- **Sheet16 vs Leads Match**: 675 out of 675 rows (100%) match existing records in the `Leads` sheet.
- **Genuinely New Contacts**: 0.
- **Total Pipeline in Complete Dataset**: Amin has **1,325 contacts** in the complete dataset.

#### 4. Ghaida
- **Existing Live Count**: Baseline not fully seeded.
- **Source Rows in Sheet16**: 493.
- **Phone Validation**: 490 rows have digits; 486 unique phone numbers; 3 rows have missing phone numbers.
- **Intra-sheet Duplicates**: 1 duplicate row pair in `Sheet16`.
- **Sheet16 vs Leads Match**: 493 out of 493 rows (100%) match existing records in the `Leads` sheet.
- **Genuinely New Contacts**: 0.
- **Total Pipeline in Complete Dataset**: Ghaida has **1,322 contacts** in the complete dataset.

#### 5. Unassigned & Invalid Rows
- **Total Rows in Sheet16**: 7.
- **Invalid / Excluded**: Row 67 is completely empty (no name, phone, email, notes). Excluded by reconciler.
- **Valid Rows**: 6 rows without assigned salesperson. All 6 matched records in the `Leads` sheet.
- **Total Unassigned in Complete Dataset**: 6 contacts.

---

## 4. Companies Analysis & Pagination Fix

### 4.1 Workbook Company Entity Reconciliation
- **Total Rows in Sheet `Companies`**: 4,040 rows.
- **Repeated Header Rows**: 14 rows contained repeated table headers (`"Company Name"`, `"Company"`).
- **Duplicate Rows**: 325 rows were duplicates of existing company names across different category blocks.
- **Distinct Enterprise Companies**: **3,701 unique names** (case-insensitive, normalized).
- **Companies Created from Contacts**: 2,746 companies.
- **Pre-seeding Logic**: `extract_company_names()` in `workbook_reader.py` extracts all 3,701 unique company names and pre-seeds any company entities not already created during contact insertion.

### 4.2 Companies UI & Pagination Enhancements
- **Fixed Sort By Parameter**: Corrected sort direction toggling in `CompaniesPage.tsx`, removing the buggy `sortBy.slice(1)`.
- **Deduplicated Append**: Prevented duplicate React table keys by keying and filtering existing company IDs on successive "Load More" page appends.
- **Debounced Server-Side Search**: Added a 300ms debounced server-side search input that queries `/companies?search=...` across the full 3,701 dataset, resetting pagination smoothly.
- **Stable Tie-Breaker**: Added `.order_by(Company.id.asc())` to backend queries to guarantee deterministic pagination without row skips.

---

## 5. Contacts Position Restoration & Lead Numbering

### 5.1 Working Position Preservation
- **State Storage**: Scoped exclusively to `sessionStorage` under `crm_contacts_pos_${userId}`. No database schema changes, zero cross-user leakage.
- **Session Cleanup**: `logout()` in `authStore.ts` cleans all `crm_contacts_pos_*` keys.
- **Preserved Properties**:
  - `activeView` (`'LEADS' | 'EMAIL_WHATSAPP' | 'ARCHIVE'`)
  - `search` text
  - `ownerFilter`, `outcomeFilter`, `countryFilter`, `industryFilter`, `positionFilter`
  - `sortBy` and `sortDir`
  - `loadedPages` (e.g. 9 pages to reach contact 430)
  - `scrollY` (exact pixel offset)
  - `anchorContactId` (visible DOM contact row id for `scrollIntoView`)
- **Restoration Timing**:
  - Filters, view, and query state are restored *before* issuing network requests.
  - When returning with `loadedPages > 1`, contacts are fetched up to `pagesToLoad * PER_PAGE` (the backend allows `limit` up to 5,000).
  - Once rows render, `requestAnimationFrame` scrolls the target `contact-row-${anchorContactId}` into view, with graceful fallback to `scrollY`.
  - Intentional user filter or search changes immediately reset pagination to page 1.

### 5.2 Compact Sequential Lead Numbering (`#`)
- **Table Structure**:
  - Sticky `#` column header with width `48px`, `left: 0` (or `right: 0` in RTL).
  - Contact Name sticky offset adjusted to `left: 48px`.
  - Company sticky offset adjusted to `left: 238px`.
- **Sequential Formula**:
  - Display number = `index + 1` across all loaded contacts in the infinite list.
  - Page 1 (50 rows): 1–50.
  - Page 9 (450 rows): 1–450 (Contact 430 displays `# 430`).
- **Deterministic Ordering**:
  - Added `.order_by(Contact.id.asc())` tie-breaker to all sorting branches in `backend/app/contacts/service.py`.

---

## 6. Verification & Test Results

### 6.1 Backend Automated Tests
- **Reconciliation & Normalization Suite**:
  ```powershell
  $env:PYTHONPATH="backend"; backend\.venv\Scripts\python -m pytest backend/tests/unit/test_gulf_import_reconciler.py backend/tests/unit/test_gulf_import_normalizers.py -v
  ```
  - **Result**: `60 passed in 0.63s` (100% pass).
- **Core Security & Backfill Tests**:
  - `test_security.py`: 5 passed.
  - `test_verification_backfill.py`: 5 passed.
  - `test_auto_migrate_transactions.py`: 2 passed.

### 6.2 Frontend Production Build
- **Build Command**:
  ```powershell
  npm --prefix frontend run build
  ```
  - **Type Check**: `tsc` passed without any errors.
  - **Vite Production Bundle**:
    - `dist/index.html`: 1.49 kB
    - `dist/assets/index-Wk0x5NCq.css`: 28.42 kB
    - `dist/assets/index-CQnOm5Bi.js`: 1,161.80 kB
    - **Status**: Built successfully in 11.44s.

---

## 7. Production Deployment & Database Import Instructions

To apply these fixes and import the complete Gulf dataset into the live production database:

### Step 1: Push Feature Branch & Open PR
```bash
git push origin fix/contacts-position-numbering-and-gulf-reconciliation
```

### Step 2: Run Production Import Command
With `DATABASE_URL` pointing to the live production PostgreSQL instance, run:
```bash
python backend/scripts/import_leads.py --file "Gulf Leads  (1).xlsx"
```
*Note: The script is idempotent. Running it multiple times produces 0 duplicate contacts or companies and safely preserves all call histories, notes, and demo appointments.*

### Step 3: Verify Live Counts
Run SQL count check against the production database:
```sql
SELECT u.email, u.first_name, COUNT(c.id) AS total_contacts
FROM users u
LEFT JOIN contacts c ON c.owner_id = u.id AND c.deleted_at IS NULL
GROUP BY u.email, u.first_name
ORDER BY total_contacts DESC;
```
Expected output:
- **Saleh**: 1,325 contacts
- **Amin**: 1,325 contacts
- **Ghaida**: 1,322 contacts
- **Hassan**: 1,231 contacts
- **Unassigned**: 6 contacts
- **Total**: 5,209 contacts
- **Unique Companies**: 3,701 companies
