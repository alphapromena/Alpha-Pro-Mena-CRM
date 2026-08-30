"""
File Data Ingestion Service for CSV, XLSX, and XLS files.
Unified pipeline adhering to the google-sheets-data-integration & etl-pipeline-validator standards.
"""
import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import structlog
from fastapi import UploadFile
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError, AppError
from app.core.security import normalize_email, normalize_phone
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.company import Company
from app.models.user import User
from app.models.audit import AuditLog

logger = structlog.get_logger(__name__)


class FileImportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_file_to_rows(self, file_content: bytes, filename: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse raw uploaded file bytes into a list of headers and list of row dicts.
        Supports .csv and .xlsx files.
        """
        lower_name = filename.lower()
        if lower_name.endswith(".csv"):
            return self._parse_csv(file_content)
        elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
            return self._parse_excel(file_content)
        else:
            raise ValidationError(f"Unsupported file format. Please upload a .csv, .xlsx, or .xls file.")

    def _parse_csv(self, content: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
        # Try UTF-8 first, fallback to cp1256 (Arabic) or latin1
        text = None
        for enc in ["utf-8-sig", "utf-8", "cp1256", "latin1"]:
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = content.decode("utf-8", errors="ignore")

        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return [], []

        # Header detection
        headers = [str(col).strip() for col in rows[0]]
        # Filter empty headers
        headers = [h if h else f"Column_{i+1}" for i, h in enumerate(headers)]

        data_rows: List[Dict[str, Any]] = []
        for r in rows[1:]:
            if not any(str(c).strip() for c in r):
                continue
            row_dict = {}
            for i, val in enumerate(r):
                if i < len(headers):
                    row_dict[headers[i]] = str(val).strip()
            data_rows.append(row_dict)

        return headers, data_rows

    def _parse_excel(self, content: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            wb.close()
        except Exception as e:
            logger.error("excel_parse_error", error=str(e))
            raise ValidationError(f"Could not read Excel file: {str(e)}")

        if not rows:
            return [], []

        headers = [str(col).strip() if col is not None else f"Column_{i+1}" for i, col in enumerate(rows[0])]
        headers = [h if h else f"Column_{i+1}" for i, h in enumerate(headers)]

        data_rows: List[Dict[str, Any]] = []
        for r in rows[1:]:
            if not any(c is not None and str(c).strip() for c in r):
                continue
            row_dict = {}
            for i, val in enumerate(r):
                if i < len(headers):
                    val_str = ""
                    if val is not None:
                        # Handle datetime or float phone numbers
                        if isinstance(val, float) and val.is_integer():
                            val_str = str(int(val))
                        else:
                            val_str = str(val).strip()
                    row_dict[headers[i]] = val_str
            data_rows.append(row_dict)

        return headers, data_rows

    def detect_column_mapping(self, headers: List[str]) -> Dict[str, str]:
        """
        Auto-detect column mapping matching Google Sheet / CRM schema.
        """
        mapping = {}
        header_lower_map = {h.lower().strip(): h for h in headers}

        # Field patterns
        patterns = {
            "first_name": ["first name", "firstname", "first", "name", "full name", "الاسم الاول", "الاسم"],
            "last_name": ["last name", "lastname", "last", "surname", "اسم العائلة", "الكنية"],
            "email": ["email", "e-mail", "email address", "البريد الالكتروني", "ايميل"],
            "phone": ["phone", "phone number", "mobile", "telephone", "cell", "رقم الهاتف", "الجوال"],
            "company": ["company", "company name", "organization", "account", "الشركة", "اسم الشركة"],
            "position": ["position", "job title", "title", "role", "المنصب", "المسمى الوظيفي"],
            "country": ["country", "nation", "location", "الدولة", "البلد"],
            "industry": ["industry", "sector", "القطاع", "مجال العمل"],
            "source": ["source", "lead source", "المصدر"],
        }

        for field, keywords in patterns.items():
            for kw in keywords:
                for h_lower, orig_h in header_lower_map.items():
                    if kw == h_lower or kw in h_lower:
                        if field not in mapping:
                            mapping[field] = orig_h
                            break
                if field in mapping:
                    break

        return mapping

    async def preview_import(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Preview uploaded file without writing to database.
        """
        headers, data_rows = await self.parse_file_to_rows(file_content, filename)
        detected_mapping = self.detect_column_mapping(headers)

        preview_rows = data_rows[:20]

        return {
            "filename": filename,
            "total_rows": len(data_rows),
            "headers": headers,
            "preview_rows": preview_rows,
            "detected_mapping": detected_mapping,
        }

    async def execute_import(
        self,
        file_content: bytes,
        filename: str,
        column_mapping: Optional[Dict[str, str]],
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Execute full import using the unified CRM data pipeline.
        Feeds unassigned leads with relative sheet order into New Leads Pool.
        """
        headers, data_rows = await self.parse_file_to_rows(file_content, filename)
        mapping = column_mapping or self.detect_column_mapping(headers)

        # Get current maximum sheet_order in DB
        max_order_stmt = select(func.coalesce(func.max(Contact.sheet_order), 0)).where(Contact.deleted_at.is_(None))
        max_order = (await self.db.execute(max_order_stmt)).scalar_one()

        rows_ready = 0
        rows_duplicate = 0
        rows_invalid = 0
        rows_error = 0
        created_contacts: List[Contact] = []
        error_details: List[str] = []

        batch_id = uuid.uuid4().hex[:8]

        for idx, row in enumerate(data_rows, start=1):
            try:
                first_name = str(row.get(mapping.get("first_name", "First Name"), "")).strip() or None
                last_name = str(row.get(mapping.get("last_name", "Last Name"), "")).strip() or None
                email_raw = str(row.get(mapping.get("email", "Email"), "")).strip() or None
                phone_raw = str(row.get(mapping.get("phone", "Phone"), "")).strip() or None
                company_raw = str(row.get(mapping.get("company", "Company"), "")).strip() or None
                position = str(row.get(mapping.get("position", "Position"), "")).strip() or None
                country = str(row.get(mapping.get("country", "Country"), "")).strip() or None
                industry = str(row.get(mapping.get("industry", "Industry"), "")).strip() or None
                source = str(row.get(mapping.get("source", "Source"), "File Upload")).strip() or "File Upload"

                # Validation: must have at least one identifier
                if not first_name and not email_raw and not phone_raw:
                    rows_invalid += 1
                    continue

                if not first_name:
                    first_name = email_raw.split("@")[0] if email_raw else "Lead"

                norm_email = normalize_email(email_raw) if email_raw else None
                norm_phone = normalize_phone(phone_raw) if phone_raw else None

                if norm_email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", norm_email):
                    rows_invalid += 1
                    error_details.append(f"Row {idx}: Invalid email format ({email_raw})")
                    continue

                # Deterministic Idempotency Key
                import_key = hashlib.sha256(
                    f"upload:{filename}:{batch_id}:{idx}".encode()
                ).hexdigest()

                # Duplicate Check
                existing_contact = None
                if norm_email:
                    existing_contact = (
                        await self.db.execute(select(Contact).where(Contact.normalized_email == norm_email, Contact.deleted_at.is_(None)))
                    ).scalar_one_or_none()
                elif norm_phone:
                    existing_contact = (
                        await self.db.execute(select(Contact).where(Contact.normalized_phone == norm_phone, Contact.deleted_at.is_(None)))
                    ).scalar_one_or_none()

                if existing_contact:
                    rows_duplicate += 1
                    continue

                # Company association or creation
                company_id = None
                if company_raw:
                    comp_stmt = select(Company).where(Company.name.ilike(company_raw), Company.deleted_at.is_(None))
                    existing_comp = (await self.db.execute(comp_stmt)).scalar_one_or_none()
                    if existing_comp:
                        company_id = existing_comp.id
                    else:
                        new_comp = Company(name=company_raw, industry=industry, country=country)
                        self.db.add(new_comp)
                        await self.db.flush()
                        company_id = new_comp.id

                # Historical attempts from columns like "1st Attempt", "2nd Attempt"
                att_1 = str(row.get("1st Attempt", "") or row.get("1st Attempts", "") or row.get("Attempt 1", "")).strip() or None
                att_2 = str(row.get("2nd Attempt", "") or row.get("2nd Attempts", "") or row.get("Attempt 2", "")).strip() or None
                att_3 = str(row.get("3rd Attempt", "") or row.get("3rd Attempts", "") or row.get("Attempt 3", "")).strip() or None

                attempt_count = sum(1 for a in [att_1, att_2, att_3] if a)
                last_outcome = att_3 or att_2 or att_1 or None

                new_contact = Contact(
                    id=uuid.uuid4(),
                    first_name=first_name,
                    last_name=last_name,
                    email=email_raw,
                    normalized_email=norm_email,
                    phone=phone_raw,
                    normalized_phone=norm_phone,
                    company_id=company_id,
                    position=position,
                    country=country,
                    industry=industry,
                    source=source,
                    source_sheet=filename,
                    status=ContactStatus.UNASSIGNED,
                    priority=ContactPriority.MEDIUM,
                    sheet_order=max_order + idx,
                    import_key=import_key,
                    attempt_1=att_1,
                    attempt_2=att_2,
                    attempt_3=att_3,
                    attempt_count=attempt_count,
                    last_outcome=last_outcome,
                )
                self.db.add(new_contact)
                created_contacts.append(new_contact)
                rows_ready += 1

            except Exception as row_err:
                rows_error += 1
                error_details.append(f"Row {idx}: {str(row_err)}")
                logger.error("file_import_row_error", row=idx, error=str(row_err))

        await self.db.commit()

        # Audit log entry
        audit = AuditLog(
            actor_id=user_id,
            action="lead.file_import",
            entity_type="Contact",
            entity_id=user_id,
            new_value={
                "filename": filename,
                "rows_ready": rows_ready,
                "rows_duplicate": rows_duplicate,
                "rows_invalid": rows_invalid,
                "rows_error": rows_error,
            },
            notes=f"Imported {rows_ready} leads from {filename}",
        )
        self.db.add(audit)
        await self.db.commit()

        logger.info(
            "file_import.completed",
            filename=filename,
            ready=rows_ready,
            duplicates=rows_duplicate,
            invalid=rows_invalid,
            errors=rows_error,
        )

        return {
            "filename": filename,
            "total_processed": len(data_rows),
            "rows_ready": rows_ready,
            "rows_duplicate": rows_duplicate,
            "rows_invalid": rows_invalid,
            "rows_error": rows_error,
            "error_details": error_details[:10],
        }
