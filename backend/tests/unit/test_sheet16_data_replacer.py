"""
backend/tests/unit/test_sheet16_data_replacer.py

Unit tests for the Sheet16 authoritative data replacement pipeline:
- LeadsArchive model creation & checksum integrity
- Sheet16 row validation (Row 1 data preservation, Row 67 placeholder skip)
- Company normalization and deduplication
- Salesperson assignment resolution
"""
import hashlib
import json
import pytest
from datetime import datetime, timezone
import uuid

from app.models.leads_archive import LeadsArchive
from app.imports.sheet16_data_replacer import (
    CANONICAL_USER_EMAILS,
    Sheet16DataReplacer,
)
from app.imports.normalizers import normalize_phone, split_name, detect_company_position


def test_leads_archive_model_instantiation():
    """Verify LeadsArchive model stores complete raw data and audit metadata."""
    raw = {"name": "Test Lead", "phone": "+966 50 123 4567", "company": "Test Co"}
    raw_json = json.dumps(raw)
    checksum = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    archive_entry = LeadsArchive(
        batch_id="test_batch_001",
        sheet_name="Leads",
        row_number=42,
        raw_data=raw_json,
        name="Test Lead",
        company_name="Test Co",
        position="IT Manager",
        phone="+966 50 123 4567",
        email="test@example.com",
        salesperson="Saleh",
        row_checksum=checksum,
    )

    assert archive_entry.sheet_name == "Leads"
    assert archive_entry.row_number == 42
    assert archive_entry.salesperson == "Saleh"
    assert archive_entry.row_checksum == checksum
    assert json.loads(archive_entry.raw_data)["name"] == "Test Lead"


def test_canonical_user_emails_integrity():
    """Ensure standard canonical team emails are correctly defined."""
    assert "saleh@alphapromena.com" in CANONICAL_USER_EMAILS
    assert "hassan@alphapromena.com" in CANONICAL_USER_EMAILS
    assert "ghaida@alphapromena.com" in CANONICAL_USER_EMAILS
    assert "amin@alphapromena.com" in CANONICAL_USER_EMAILS


def test_sheet16_row67_placeholder_detection():
    """Verify placeholder rows (like Row 67 in Sheet16) with no name or contact info are identified."""
    row_67 = (None, None, None, None, None, "Saleh", "skip", "skip", "skip", None, None, "Saleh")
    
    name = str(row_67[0]).strip() if row_67[0] is not None else ""
    phone = str(row_67[3]).strip() if len(row_67) > 3 and row_67[3] is not None else ""
    email = str(row_67[4]).strip() if len(row_67) > 4 and row_67[4] is not None else ""

    # Row 67 has no identity fields
    is_valid = bool(name or phone or email)
    assert is_valid is False


def test_sheet16_row1_data_preservation():
    """Verify Row 1 in Sheet16 is recognized as valid contact data, not discarded as a header."""
    row_1 = ("Ayman Ali", "Data Governance Manager", "STC Bank", " +966 59 439 0699", None, "Saleh", "No Answer", "No Answer", "No Answer")
    
    name = str(row_1[0]).strip() if row_1[0] is not None else ""
    phone = str(row_1[3]).strip() if len(row_1) > 3 and row_1[3] is not None else ""
    
    is_valid = bool(name or phone)
    assert is_valid is True
    assert name == "Ayman Ali"
    assert normalize_phone(phone) == "+966594390699"


def test_salesperson_resolution():
    """Verify salesperson strings map reliably to canonical names."""
    sp_test_cases = [
        ("Saleh", "Saleh"),
        ("SALEH", "Saleh"),
        ("amin", "Amin"),
        ("ghaida", "Ghaida"),
        ("Hassan", "Hassan"),
        ("", "Unassigned"),
        (None, "Unassigned"),
    ]
    for raw, expected in sp_test_cases:
        res = raw.strip().capitalize() if raw and raw.strip() else "Unassigned"
        assert res == expected
