# Google Sheets Integration Guide

## 1. Synchronization Architecture

```
[ Google Spreadsheet ]
          │ (Google Service Account OAuth 2.0)
          ▼
[ Sheets Ingestion Worker ]
          │
          ├── 1. Read row ranges (A:Z)
          ├── 2. Map dynamic columns (First Name, Email, Phone, Company, etc.)
          ├── 3. Validate & Normalize (RFC 5322 Email, E.164 Phone)
          ├── 4. Compute Idempotency Hash: sha256(sheet_id + sheet_name + row_idx)
          ├── 5. Check Duplicate Contacts (Exact Email or Normalized Phone match)
          │
          ▼
[ Unassigned Lead Pool ] ──► [ Admin Multi-Strategy Distribution ] ──► [ Sales Rep ]
```

## 2. Setting Up Google Cloud Service Account

1. Go to **Google Cloud Console** and create a new project.
2. Enable the **Google Sheets API**.
3. Create a **Service Account** and generate a JSON private key.
4. Copy the service account email (e.g., `alphapro-sync@project-id.iam.gserviceaccount.com`).
5. Open your target Google Sheet, click **Share**, and grant **Viewer** permissions to the service account email.
6. Configure `.env`:
```env
GOOGLE_SERVICE_ACCOUNT_EMAIL=alphapro-sync@project-id.iam.gserviceaccount.com
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvgIBA...-----END PRIVATE KEY-----\n"
```
7. Open **Admin > Google Sheets Sync** in the CRM UI and configure the spreadsheet ID and column mappings.
