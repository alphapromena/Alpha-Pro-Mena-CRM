"""
Google Sheets Sync Service — Idempotent lead ingestion pipeline.
Follows google-sheets-data-integration skill guidelines.

Extended to use app.imports reconciliation library so that:
- Legacy contacts (without import_key) are matched by phone or email.
- Owner resolution uses the same authoritative salesperson map.
- Aseel (DATA_OPS) is never assigned as the owner of imported contacts.
- DNC contacts are never overwritten.
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
from app.core.security import normalize_email as core_normalize_email
from app.core.security import normalize_phone as core_normalize_phone
from app.imports.normalizers import normalize_email as import_normalize_email
from app.imports.normalizers import normalize_phone as import_normalize_phone
from app.imports.normalizers import make_import_key
from app.imports.db_writer import (
    get_or_create_company,
    load_db_snapshot,
    resolve_salesperson_map,
)
from app.imports.reconciler import match_to_db
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.company import Company
from app.models.user import User
from app.models.integrations import GoogleSheetsSyncConfig, GoogleSheetsSyncRun, SyncErrorLog

logger = structlog.get_logger(__name__)
settings = get_settings()

# Lazily cached per-sync-run; reset at the start of each run_sync call
_SHEETS_COMPANY_CACHE: Dict[str, uuid.UUID] = {}


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

        # Pre-load DB snapshot and salesperson map once per sync run
        self._db_snapshot = await load_db_snapshot(self.db)
        self._sp_map = await resolve_salesperson_map(self.db)
        self._company_cache: Dict[str, uuid.UUID] = {}

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

        # Use reconciler normalizers (conservative — no auto country-code expansion)
        norm_email = import_normalize_email(email_raw) if email_raw else None
        norm_phone = import_normalize_phone(phone_raw) if phone_raw else None

        if norm_email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", norm_email):
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

        # Build a minimal LeadRow for snapshot matching (no full parse needed)
        from app.imports.workbook_reader import LeadRow
        import_key = make_import_key(
            email=norm_email or "",
            phone=norm_phone or "",
            first_name=first_name,
            last_name=last_name,
        )
        probe_row = LeadRow(
            first_name=first_name, last_name=last_name,
            normalized_email=norm_email or "",
            normalized_phone=norm_phone or "",
            import_key=import_key,
        )

        # Match against DB snapshot (includes legacy contacts without import_key)
        snap = getattr(self, "_db_snapshot", None)
        existing_id = None
        if snap is not None:
            existing_id, _reason = match_to_db(probe_row, snap)
        else:
            # Fallback for test contexts without pre-loaded snapshot
            if norm_email:
                r = await self.db.execute(
                    select(Contact.id).where(
                        Contact.normalized_email == norm_email,
                        Contact.deleted_at.is_(None),
                    )
                )
                row_ = r.scalar_one_or_none()
                if row_:
                    existing_id = row_
            if not existing_id and norm_phone:
                r = await self.db.execute(
                    select(Contact.id).where(
                        Contact.normalized_phone == norm_phone,
                        Contact.deleted_at.is_(None),
                    )
                )
                row_ = r.scalar_one_or_none()
                if row_:
                    existing_id = row_

        # Salesperson resolution — uses authoritative map, excludes Aseel
        owner_id = None
        sales_person_raw = str(
            row_dict.get(mapping.get("sales_person", "Sales Person"), "")
            or row_dict.get("Sales Person", "")
            or row_dict.get("Salesperson", "")
            or row_dict.get("Owner", "")
        ).strip()
        sp_map = getattr(self, "_sp_map", {})
        if sales_person_raw:
            sp_lower = sales_person_raw.lower()
            if sp_lower in sp_map:
                owner_id = sp_map[sp_lower]
            else:
                # Partial match fallback
                for key, uid in sp_map.items():
                    if key in sp_lower or sp_lower in key:
                        owner_id = uid
                        break

        # Company association or creation (uses shared cache to prevent duplicates)
        company_cache = getattr(self, "_company_cache", {})
        company_id = await get_or_create_company(self.db, company_raw, company_cache)

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

        # Load full existing_contact if we have an id
        existing_contact = None
        if existing_id is not None:
            res = await self.db.execute(
                select(Contact).where(
                    Contact.id == existing_id,
                    Contact.deleted_at.is_(None),
                )
            )
            existing_contact = res.scalar_one_or_none()

        if existing_contact:
            run.rows_duplicate += 1
            # Never touch DNC contacts
            if existing_contact.is_dnc:
                return
            # Enrich blank fields only — never overwrite non-blank CRM values
            changed = False
            if not existing_contact.email and email_raw:
                existing_contact.email = email_raw
                existing_contact.normalized_email = norm_email
                changed = True
            if not existing_contact.phone and phone_raw:
                existing_contact.phone = phone_raw
                existing_contact.normalized_phone = norm_phone
                changed = True
            if not existing_contact.company_id and company_id:
                existing_contact.company_id = company_id
                changed = True
            if not existing_contact.position and position:
                existing_contact.position = position
                changed = True
            if not existing_contact.owner_id and owner_id:
                existing_contact.owner_id = owner_id
                changed = True
            if not existing_contact.import_key and import_key:
                existing_contact.import_key = import_key
                changed = True
            if changed:
                self.db.add(existing_contact)
                await self.db.flush()
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
