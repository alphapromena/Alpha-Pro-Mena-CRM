"""
tests/unit/test_gulf_import_normalizers.py

Unit tests for the normalizers module.
These tests cover phone normalization, email normalization,
import key generation, name splitting, and B/C column detection.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-32-chars-long-1234")
os.environ.setdefault("JWT_SECRET_KEY",  "test-jwt-secret-key-32-chars-long")
os.environ.setdefault("APP_ENV", "test")

import pytest
from app.imports.normalizers import (
    normalize_phone,
    normalize_email,
    make_import_key,
    split_name,
    detect_company_position,
    phones_could_match,
)


# ── normalize_phone ───────────────────────────────────────────────────────────

class TestNormalizePhone:
    def test_blank_returns_empty(self):
        assert normalize_phone(None) == ""
        assert normalize_phone("") == ""
        assert normalize_phone("  ") == ""

    def test_placeholder_returns_empty(self):
        assert normalize_phone("N/A") == ""
        assert normalize_phone("None") == ""
        assert normalize_phone("-") == ""

    def test_saudi_05x_expanded_with_hint(self):
        result = normalize_phone("0559123456", country_hint="SA")
        assert result == "+966559123456"

    def test_saudi_05x_NOT_expanded_without_hint(self):
        """Without country_hint, 05x must NOT be auto-expanded to +966."""
        result = normalize_phone("0559123456")
        assert result == "0559123456"
        assert "+966" not in result

    def test_already_e164_unchanged(self):
        assert normalize_phone("+966501234567") == "+966501234567"
        assert normalize_phone("+97150123456")  == "+97150123456"

    def test_oman_expanded_with_hint(self):
        result = normalize_phone("0912345678", country_hint="OM")
        assert result == "+968912345678"

    def test_strips_spaces_and_dashes(self):
        result = normalize_phone("+966 50-123-4567")
        assert result == "+966501234567"

    def test_uae_hint_expansion(self):
        result = normalize_phone("0501234567", country_hint="AE")
        assert result == "+971501234567"

    def test_no_digits_returns_empty(self):
        assert normalize_phone("abc") == ""


# ── normalize_email ───────────────────────────────────────────────────────────

class TestNormalizeEmail:
    def test_lowercases(self):
        assert normalize_email("Test@Example.COM") == "test@example.com"

    def test_strips_whitespace(self):
        assert normalize_email("  user@domain.com  ") == "user@domain.com"

    def test_placeholder_returns_empty(self):
        assert normalize_email("N/A") == ""
        assert normalize_email("n/a") == ""

    def test_missing_at_returns_empty(self):
        assert normalize_email("notanemail") == ""

    def test_none_returns_empty(self):
        assert normalize_email(None) == ""


# ── make_import_key ───────────────────────────────────────────────────────────

class TestMakeImportKey:
    def test_email_priority_over_phone(self):
        key_email = make_import_key(email="test@example.com", phone="+966501234567",
                                     first_name="Ahmed")
        key_noemail = make_import_key(email="", phone="+966501234567", first_name="Ahmed")
        assert key_email != key_noemail

    def test_same_email_same_key(self):
        k1 = make_import_key(email="user@test.com")
        k2 = make_import_key(email="user@test.com", phone="+966501111111", first_name="X")
        assert k1 == k2   # email wins

    def test_phone_plus_name_key(self):
        k1 = make_import_key(phone="+966501234567", first_name="Mohammed", last_name="Ali")
        k2 = make_import_key(phone="+966501234567", first_name="Mohammed", last_name="Ali")
        assert k1 == k2

    def test_name_only_key(self):
        k1 = make_import_key(first_name="Fatima", last_name="Hassan", company="Corp")
        k2 = make_import_key(first_name="Fatima", last_name="Hassan", company="Corp")
        assert k1 == k2

    def test_different_names_different_keys(self):
        k1 = make_import_key(first_name="Ahmed", last_name="Ali", company="Corp")
        k2 = make_import_key(first_name="Saeed", last_name="Ali", company="Corp")
        assert k1 != k2


# ── split_name ────────────────────────────────────────────────────────────────

class TestSplitName:
    def test_two_word_name(self):
        assert split_name("Ahmed Hassan") == ("Ahmed", "Hassan")

    def test_three_word_arabic_name(self):
        # Last word becomes last_name
        assert split_name("Mohammed Ali Hassan") == ("Mohammed Ali", "Hassan")

    def test_arabic_two_word(self):
        first, last = split_name("مها الشمري")
        assert first == "مها"
        assert last == "الشمري"

    def test_single_word(self):
        assert split_name("Ahmed") == ("Ahmed", "")

    def test_none_returns_empty(self):
        assert split_name(None) == ("", "")

    def test_blank_returns_empty(self):
        assert split_name("") == ("", "")


# ── detect_company_position ───────────────────────────────────────────────────

class TestDetectCompanyPosition:
    COMPANIES = frozenset({"shawarmer", "stc solutions", "aramco"})

    def test_default_layout_b_position_c_company(self):
        pos, co = detect_company_position("Manager", "STC Solutions", self.COMPANIES)
        assert pos == "Manager"
        assert co == "STC Solutions"

    def test_reversed_when_b_is_company(self):
        """SHAWARMER block: B = company, C = position."""
        pos, co = detect_company_position("SHAWARMER", "HR Manager", self.COMPANIES)
        assert co == "SHAWARMER"
        assert pos == "HR Manager"

    def test_blank_b_returns_none_position(self):
        pos, co = detect_company_position("", "Tech Corp", self.COMPANIES)
        assert pos is None
        assert co == "Tech Corp"

    def test_blank_c_returns_none_company(self):
        pos, co = detect_company_position("Director", "", self.COMPANIES)
        assert pos == "Director"
        assert co is None

    def test_case_insensitive_company_detection(self):
        pos, co = detect_company_position("ARAMCO", "Engineer", self.COMPANIES)
        assert co == "ARAMCO"
        assert pos == "Engineer"


# ── phones_could_match ────────────────────────────────────────────────────────

class TestPhonesCouldMatch:
    def test_exact_match(self):
        assert phones_could_match("+966501234567", "+966501234567") is True

    def test_plus_prefix_difference(self):
        assert phones_could_match("+966501234567", "966501234567") is True

    def test_last_9_match(self):
        # Different country codes but same subscriber (shouldn't match)
        assert phones_could_match("+966501234567", "+971501234567") is False

    def test_empty_returns_false(self):
        assert phones_could_match("", "+966501234567") is False
        assert phones_could_match("+966501234567", "") is False

    def test_different_numbers(self):
        assert phones_could_match("+966501234567", "+966509999999") is False
