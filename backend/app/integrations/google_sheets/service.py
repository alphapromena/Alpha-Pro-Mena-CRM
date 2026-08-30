"""
Google Sheets Sync Service — Idempotent lead ingestion pipeline.
Follows google-sheets-data-integration skill guidelines.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ValidationError, AppError
from app.core.security import normalize_email, normalize_phone
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.company import Company
from app.models.user import User
from app.models.integrations import GoogleSheetsSyncConfig, GoogleSheetsSyncRun, SyncErrorLog

logger = structlog.get_logger(__name__)
settings = get_settings()


class GoogleSheetsSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_sync(
        self,
        config_id: uuid.UUID,
        triggered_by: str = "scheduler",
        triggered_by_user_id: Optional[uuid.UUID] = None,
        mock_data: Optional[List[Dict[str, Any]]] = None,
    ) -> GoogleSheetsSyncRun:
        """
        Execute Google Sheets ingestion for a given sync config.
        If real Google credentials are configured, it uses Google Sheets API.
        If mock_data is provided (e.g. testing or local dev), it processes the mock rows.
        """
        # 1. Fetch Config
        stmt = select(GoogleSheetsSyncConfig).where(GoogleSheetsSyncConfig.id == config_id)
        config = (await self.db.execute(stmt)).scalar_one_or_none()
        if not config:
            raise ValidationError("Google Sheets sync configuration not found.")

        # 2. Create Sync Run Record
        run = GoogleSheetsSyncRun(
            config_id=config.id,
            status="RUNNING",
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        await self.db.flush()

        logger.info("sheets_sync.started", config_id=str(config.id), run_id=str(run.id))

        try:
            # 3. Read Rows from Google Sheets or mock source
            rows, header = await self._fetch_rows(config, mock_data)
            run.rows_read = len(rows)

            mapping = config.column_mapping or {
                "first_name": "First Name",
                "last_name": "Last Name",
                "email": "Email",
                "phone": "Phone",
                "company": "Company",
                "position": "Position",
                "country": "Country",
                "industry": "Industry",
                "source": "Source",
            }

            # 4. Process Rows
            for idx, row in enumerate(rows, start=config.last_row_index + 1 if not mock_data else 1):
                try:
                    await self._process_row(config, run, row, idx, mapping)
                except Exception as row_err:
                    run.rows_error += 1
                    error_log = SyncErrorLog(
                        sync_run_id=run.id,
                        row_index=idx,
                        error_message=str(row_err),
                        raw_value=json.dumps(row, default=str),
                    )
                    self.db.add(error_log)

            run.status = "COMPLETED"
            run.completed_at = datetime.now(timezone.utc)
            config.last_synced_at = datetime.now(timezone.utc)
            if not mock_data:
                config.last_row_index += len(rows)
            self.db.add(config)
            self.db.add(run)
            await self.db.flush()

            logger.info(
                "sheets_sync.completed",
                run_id=str(run.id),
                imported=run.rows_imported,
                duplicates=run.rows_duplicate,
                errors=run.rows_error,
            )
            return run

        except Exception as e:
            run.status = "FAILED"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            self.db.add(run)
            await self.db.flush()
            logger.error("sheets_sync.failed", run_id=str(run.id), error=str(e))
            raise

    async def _fetch_rows(
        self, config: GoogleSheetsSyncConfig, mock_data: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Read data rows using google-api-python-client or mock fallback."""
        if mock_data is not None:
            return mock_data, list(mock_data[0].keys()) if mock_data else []

        if not settings.google_sheets_enabled:
            # Return empty or sample if no service account credentials provided
            logger.warning("sheets_sync.no_credentials_configured", spreadsheet_id=config.spreadsheet_id)
            return [], []

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds_info = {
                "client_email": settings.google_service_account_email,
                "private_key": settings.google_service_account_private_key.replace("\\n", "\n"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            credentials = service_account.Credentials.from_service_account_info(
                creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            service = build("sheets", "v4", credentials=credentials)
            sheet = service.spreadsheets()
            range_name = f"{config.sheet_name}!{config.range}"
            result = sheet.values().get(spreadsheetId=config.spreadsheet_id, range=range_name).execute()
            values = result.get("values", [])

            if not values:
                return [], []

            header = values[0]
            rows = []
            for row in values[1:]:
                # Pad row to match header length
                padded = row + [""] * (len(header) - len(row))
                rows.append(dict(zip(header, padded)))
            return rows, header

        except Exception as e:
            logger.error("sheets_sync.api_error", error=str(e))
            raise AppError(f"Google Sheets API error: {str(e)}")

    async def _process_row(
        self,
        config: GoogleSheetsSyncConfig,
        run: GoogleSheetsSyncRun,
        row_dict: Dict[str, Any],
        row_index: int,
        mapping: Dict[str, str],
    ) -> None:
        # Extract fields based on mapping
        first_name = str(row_dict.get(mapping.get("first_name", "First Name"), "")).strip()
        last_name = str(row_dict.get(mapping.get("last_name", "Last Name"), "")).strip()
        email_raw = str(row_dict.get(mapping.get("email", "Email"), "")).strip()
        phone_raw = str(row_dict.get(mapping.get("phone", "Phone"), "")).strip()
        company_raw = str(row_dict.get(mapping.get("company", "Company"), "")).strip()
        position = str(row_dict.get(mapping.get("position", "Position"), "")).strip() or None
        country = str(row_dict.get(mapping.get("country", "Country"), "")).strip() or None
        industry = str(row_dict.get(mapping.get("industry", "Industry"), "")).strip() or None
        source = str(row_dict.get(mapping.get("source", "Source"), "Google Sheets")).strip()

        # Validation
        if not first_name and not email_raw and not phone_raw:
            run.rows_skipped += 1
            return

        if not first_name:
            first_name = email_raw.split("@")[0] if email_raw else "Lead"

        norm_email = normalize_email(email_raw) if email_raw else None
        norm_phone = normalize_phone(phone_raw) if phone_raw else None

        if norm_email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", norm_email):
            # Invalid email format
            run.rows_error += 1
            self.db.add(
                SyncErrorLog(
                    sync_run_id=run.id,
                    row_index=row_index,
                    field_name="email",
                    error_message=f"Invalid email format: {email_raw}",
                    raw_value=email_raw,
                )
            )
            return

        # Deterministic Idempotency Key
        import_key = hashlib.sha256(
            f"{config.spreadsheet_id}:{config.sheet_name}:{row_index}".encode()
        ).hexdigest()

        # Check for exact duplicate in CRM (by email, phone, or import key)
        existing_contact = None
        if norm_email:
            existing_contact = (
                await self.db.execute(select(Contact).where(Contact.normalized_email == norm_email, Contact.deleted_at.is_(None)))
            ).scalar_one_or_none()
        elif norm_phone:
            existing_contact = (
                await self.db.execute(select(Contact).where(Contact.normalized_phone == norm_phone, Contact.deleted_at.is_(None)))
            ).scalar_one_or_none()

        if not existing_contact and import_key:
            existing_contact = (
                await self.db.execute(select(Contact).where(Contact.import_key == import_key, Contact.deleted_at.is_(None)))
            ).scalar_one_or_none()

        # Sales Person mapping if present
        owner_id = None
        sales_person_raw = str(row_dict.get(mapping.get("sales_person", "Sales Person"), "")).strip()
        if not sales_person_raw:
            sales_person_raw = str(row_dict.get("Sales Person", "") or row_dict.get("Salesperson", "") or row_dict.get("Owner", "")).strip()
        if sales_person_raw:
            user_stmt = select(User).where(
                or_(
                    User.email.ilike(sales_person_raw),
                    User.first_name.ilike(f"%{sales_person_raw}%"),
                    (User.first_name + " " + User.last_name).ilike(f"%{sales_person_raw}%"),
                )
            ).limit(1)
            matched_user = (await self.db.execute(user_stmt)).scalar_one_or_none()
            if matched_user:
                owner_id = matched_user.id

        # Company association or creation
        company_id = None
        if company_raw:
            comp_stmt = select(Company).where(Company.name.ilike(company_raw))
            existing_company = (await self.db.execute(comp_stmt)).scalar_one_or_none()
            if existing_company:
                company_id = existing_company.id
            else:
                new_comp = Company(name=company_raw, industry=industry, country=country)
                self.db.add(new_comp)
                await self.db.flush()
                company_id = new_comp.id

        # Extract historical attempts from columns like "1st Attempts", "2nd Attempts", "3rd Attempts", "Attempt 1"
        historical_attempts = []
        for col_name, val in row_dict.items():
            if not val or not str(val).strip():
                continue
            col_lower = col_name.lower().strip()
            # Match patterns like "1st attempt", "2nd attempt", "3rd attempt", "attempt 1", "attempt 2", "attempt 3"
            attempt_num_match = re.search(r"(\d+)(?:st|nd|rd|th)?\s*attempt|attempt\s*(\d+)", col_lower)
            if attempt_num_match:
                num = int(attempt_num_match.group(1) or attempt_num_match.group(2))
                historical_attempts.append((num, str(val).strip()))

        # Sort attempts by attempt number
        historical_attempts.sort(key=lambda x: x[0])

        if existing_contact:
            run.rows_duplicate += 1
            # Idempotent skip or duplicate link
            target_contact = existing_contact
        else:
            run.rows_imported += 1
            # Ingest lead
            new_contact = Contact(
                first_name=first_name,
                last_name=last_name or None,
                email=email_raw or None,
                normalized_email=norm_email,
                phone=phone_raw or None,
                normalized_phone=norm_phone,
                company_id=company_id,
                position=position,
                country=country,
                industry=industry,
                source=source,
                campaign_id=config.campaign_id,
                status=ContactStatus.NEW if not historical_attempts else ContactStatus.CONTACTED,
                priority=ContactPriority.MEDIUM,
                import_key=import_key,
                owner_id=owner_id,  # Assigned or enters unassigned pool
                attempt_count=len(historical_attempts),
                last_outcome=historical_attempts[-1][1] if historical_attempts else None,
            )
            self.db.add(new_contact)
            await self.db.flush()
            target_contact = new_contact

            # Convert each historical attempt into an independent Call record
            from app.models.call import Call
            for att_num, att_text in historical_attempts:
                # Normalize common outcome names
                att_outcome = "OTHER"
                att_upper = att_text.upper()
                if "NO ANSWER" in att_upper or "NA" == att_upper:
                    att_outcome = "NO_ANSWER"
                elif "INTERESTED" in att_upper:
                    att_outcome = "INTERESTED"
                elif "NOT INTERESTED" in att_upper:
                    att_outcome = "NOT_INTERESTED"
                elif "EMAIL" in att_upper:
                    att_outcome = "EMAIL_REQUESTED"
                elif "WHATSAPP" in att_upper:
                    att_outcome = "WHATSAPP_REQUESTED"
                elif "CALL LATER" in att_upper or "CALLBACK" in att_upper:
                    att_outcome = "CALL_LATER"
                elif "DEMO" in att_upper:
                    att_outcome = "DEMO_REQUESTED"

                call_record = Call(
                    contact_id=target_contact.id,
                    user_id=owner_id,
                    outcome=att_outcome,
                    attempt_number=att_num,
                    duration_seconds=0,
                    notes=f"Historical attempt {att_num}: {att_text}",
                    called_at=datetime.now(timezone.utc),
                )
                self.db.add(call_record)

        await self.db.flush()
