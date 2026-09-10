"""
app.imports.normalizers — Phone / email normalisation and import-key generation.

Design constraints
------------------
- Phone numbers are preserved EXACTLY as stored in the CRM and as they appear in
  the workbook. Normalisation is applied only for COMPARISON; the raw value is
  never replaced.
- Gulf prefix expansion is applied conservatively and only when the calling context
  explicitly provides a country_hint (e.g. "SA", "AE", "QA", "OM").  A bare 05x
  number without a confirmed country hint is compared as-is to avoid silently
  creating mismatches for UAE/Oman/Bahrain numbers that also begin with 05.
- Email normalisation: lowercase + strip whitespace only.
- import_key is a stable SHA-256 of the canonical identity, keyed on the richest
  available attribute (email > normalised phone+firstname > fullname+company).
- detect_company_position resolves the B/C column ambiguity present in Sheet16.
"""
from __future__ import annotations

import hashlib
import re
from typing import FrozenSet, Optional, Tuple


# ── Known Gulf country prefixes ───────────────────────────────────────────────
_COUNTRY_DIALCODES = {
    "SA": "966",
    "AE": "971",
    "QA": "974",
    "OM": "968",
    "BH": "973",
    "KW": "965",
}


def normalize_phone(raw: object, country_hint: Optional[str] = None) -> str:
    """Return a normalised phone string for comparison purposes.

    - Non-digit characters except a leading '+' are stripped.
    - If country_hint is provided (ISO-3166-1 alpha-2, e.g. 'SA'), 10-digit
      local numbers starting with '0' are expanded to the full E.164 form.
    - Without country_hint, a '0'-prefixed local number is left as-is rather
      than risk a wrong country-code assumption.
    - Returns "" for blank / placeholder values.
    """
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text or text.lower() in ("none", "n/a", "na", "-", "--", "not found", "#n/a"):
        return ""

    digits = re.sub(r"[^\d+]", "", text)
    if not digits:
        return ""

    # Expand country-specific prefixes only when we have confirmed context
    if country_hint and country_hint.upper() in _COUNTRY_DIALCODES:
        dialcode = _COUNTRY_DIALCODES[country_hint.upper()]
        # 10-digit starting with 0 → strip leading 0 + prepend +<dialcode>
        local_pattern = re.compile(rf"^0\d{{{len(dialcode) + 1},}}$")
        if local_pattern.match(digits):
            digits = "+" + dialcode + digits[1:]
        # Already-expanded without '+': <dialcode><subscriber>
        elif digits.startswith(dialcode) and not digits.startswith("+"):
            digits = "+" + digits

    return digits


def normalize_email(raw: object) -> str:
    """Return a lowercased, stripped email for comparison. Returns '' for blanks."""
    if raw is None:
        return ""
    text = str(raw).strip().lower()
    if text in ("none", "n/a", "na", "-", "--", "#n/a"):
        return ""
    # Basic sanity: must contain @
    if "@" not in text:
        return ""
    return text


def make_import_key(
    email: str = "",
    phone: str = "",
    first_name: str = "",
    last_name: str = "",
    company: str = "",
) -> str:
    """Return a stable SHA-256 hex digest uniquely identifying one contact.

    Priority: email > phone+first_name > full_name+company.
    The same key must be reproducible from either the workbook or the DB record.
    """
    norm_email = normalize_email(email)
    # phone is already expected normalised by the caller
    first_lower = first_name.strip().lower()
    last_lower  = last_name.strip().lower()
    co_lower    = company.strip().lower()

    if norm_email:
        raw = f"email:{norm_email}"
    elif phone:
        raw = f"phone:{phone}:{first_lower}"
    else:
        raw = f"name:{first_lower}:{last_lower}:{co_lower}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def split_name(full: object) -> Tuple[str, str]:
    """Split a full name into (first, last).

    Handles Arabic and Latin names. Middle names stay in the first segment
    so that 'Mohammed Ali Hassan' → ('Mohammed Ali', 'Hassan').
    """
    if full is None:
        return ("", "")
    text = str(full).strip()
    if not text:
        return ("", "")
    parts = text.rsplit(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")


def detect_company_position(
    b_val: object,
    c_val: object,
    companies_set: FrozenSet[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve the ambiguous B/C columns found in Sheet16.

    Most rows: B = position/title, C = company name.
    Exception (e.g. SHAWARMER block): B = company name, C = position.

    Detection rule:
      If the lowercased B value appears in *companies_set* (loaded from the
      Companies worksheet), treat B as company and C as position.
      Otherwise (default): B = position, C = company.

    Returns: (position, company) — either may be None for blank cells.
    Never creates a company from a job title.
    """
    b_str = str(b_val).strip() if b_val is not None else ""
    c_str = str(c_val).strip() if c_val is not None else ""
    b_norm = b_str.lower()

    if b_norm and b_norm in companies_set:
        # B is the company name, C is the job title
        return (c_str or None, b_str or None)
    else:
        # Default: B = position/title, C = company
        return (b_str or None, c_str or None)


def phones_could_match(phone_a: str, phone_b: str) -> bool:
    """Return True if two normalised phone strings are the same subscriber.

    Handles:
    - Exact string match
    - One has a leading '+' and the other does not
    - Trailing 9-digit subscriber overlap (last 9 digits equal) ONLY within the same country

    A bare 05x local number does NOT match an international +9665x number
    unless the expansion has been confirmed by the caller via normalize_phone.
    """
    if not phone_a or not phone_b:
        return False
    if phone_a == phone_b:
        return True
    # Strip leading +
    a = phone_a.lstrip("+")
    b = phone_b.lstrip("+")
    if a == b:
        return True

    # A bare local number starting with 0 does not match an international number
    if (a.startswith("0") and not b.startswith("0")) or (b.startswith("0") and not a.startswith("0")):
        return False

    # Check known country dialcodes to prevent cross-country false positives
    cc_a = None
    for code in _COUNTRY_DIALCODES.values():
        if a.startswith(code):
            cc_a = code
            break

    cc_b = None
    for code in _COUNTRY_DIALCODES.values():
        if b.startswith(code):
            cc_b = code
            break

    if cc_a and cc_b and cc_a != cc_b:
        return False

    # Last-9 overlap within same country (sufficient to distinguish individuals within a country)
    return len(a) >= 9 and len(b) >= 9 and a[-9:] == b[-9:]
