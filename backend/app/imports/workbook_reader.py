"""
app.imports.workbook_reader — Parse Gulf Leads (1).xlsx worksheets into LeadRow objects.

Key design decisions
---------------------
- Sheet16 has NO header row. Row 1 is the first data row (Ayman Ali).
  Never skip it.
- Sheet16's B/C column order is ambiguous: most rows have B=position, C=company,
  but the SHAWARMER block (rows 693-698) has B=company, C=position.
  detect_company_position() resolves this via the Companies name set.
- The Companies tab is read only to build the company-name set; it is never
  imported as contacts.
- Rows without a name AND without a phone AND without an email are marked invalid
  (e.g. Sheet16 row 67).
- Country context: the Gulf Leads workbook is a confirmed Gulf-region dataset.
  For the Leads and Sheet16 tabs we pass country_hint="SA" (majority origin).
  Oman* tabs pass country_hint="OM".  This controls prefix expansion in
  normalize_phone() without blindly assuming every 05x number is Saudi.
- The workbook is opened with data_only=True — formula cells return None.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple, TYPE_CHECKING

from app.imports.normalizers import (
    detect_company_position,
    make_import_key,
    normalize_email,
    normalize_phone,
    split_name,
)


# ── Canonical row representation ─────────────────────────────────────────────

@dataclass
class LeadRow:
    """One canonical lead record extracted from any source sheet."""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    position: str = ""
    phone: str = ""            # raw value preserved
    normalized_phone: str = ""
    email: str = ""            # raw value preserved
    normalized_email: str = ""
    notes: str = ""
    salesperson: str = ""      # raw value from assignment column
    attempt_1_text: str = ""
    attempt_2_text: str = ""
    attempt_3_text: str = ""
    attempt_count: int = 0
    last_contacted: Optional[str] = None
    status_hint: str = "NEW"
    source_sheet: str = ""
    source_row: int = 0        # 1-based Excel row
    import_key: str = ""       # SHA-256 dedup key
    country_hint: str = ""     # ISO-3166-1 alpha-2 used during normalisation

    is_invalid: bool = False
    invalid_reason: str = ""


# ── Per-sheet configuration ───────────────────────────────────────────────────

@dataclass
class WorkbookSheetConfig:
    sheet_name: str
    has_header: bool = True
    col_name: Optional[int] = 0
    col_b: Optional[int] = None      # ambiguous column B
    col_c: Optional[int] = None      # ambiguous column C
    col_phone: Optional[int] = None
    col_email: Optional[int] = None
    col_salesperson: Optional[int] = None
    col_att1: Optional[int] = None
    col_att2: Optional[int] = None
    col_att3: Optional[int] = None
    col_last_contacted: Optional[int] = None
    col_notes: Optional[int] = None
    detect_bc_ambiguity: bool = False   # True → use companies_set
    leads_layout: bool = True           # False → B is company (standard Leads layout)
    default_salesperson: str = ""
    country_hint: str = "SA"           # Used by normalize_phone
    is_demo_sheet: bool = False


# ── Sheet configurations ──────────────────────────────────────────────────────

def _leads_like(name: str, country: str = "SA", default_sp: str = "",
                is_demo: bool = False) -> WorkbookSheetConfig:
    """Factory for sheets that share the standard Leads column layout.

    Leads: A=name, B=company, C=position, D=phone, E=email, F=salesperson,
           G=att1, H=att2, I=att3, J=last_contacted, K=notes
    """
    return WorkbookSheetConfig(
        sheet_name=name,
        has_header=True,
        col_name=0,
        col_b=1,       # company in standard layout
        col_c=2,       # position in standard layout
        detect_bc_ambiguity=False,
        leads_layout=True,
        col_phone=3, col_email=4, col_salesperson=5,
        col_att1=6, col_att2=7, col_att3=8,
        col_last_contacted=9, col_notes=10,
        country_hint=country,
        default_salesperson=default_sp,
        is_demo_sheet=is_demo,
    )


_LEADS_CONFIG    = _leads_like("Leads",       country="SA")
_GHAIDA_FU       = _leads_like("Ghaida fu",   country="SA", default_sp="Ghaida")
_AMIN_FU         = _leads_like("Amin fu",     country="SA", default_sp="Amin")
_QUSAI           = WorkbookSheetConfig(
    sheet_name="Qusai", has_header=True,
    col_name=0, col_b=1, leads_layout=True,
    col_phone=3, col_email=4, col_salesperson=5,
    country_hint="SA", default_salesperson="Qusai",
)
_DEMO_CONFIG     = _leads_like("Demo",        country="SA", is_demo=True)
_OMAN            = _leads_like("Oman",        country="OM")
_OMAN_LEADS      = _leads_like("Oman Leads ", country="OM")   # trailing space
_OMAN_LS         = _leads_like("Oman L.S",   country="OM")
_OMAN_AMIN       = _leads_like("Oman Amin ",  country="OM", default_sp="Amin")

# Sheet16: NO header row; B/C are ambiguous (detect_bc_ambiguity=True)
_SHEET16_CONFIG = WorkbookSheetConfig(
    sheet_name="Sheet16",
    has_header=False,              # Row 1 IS the first data row — do NOT skip
    col_name=0,
    col_b=1,
    col_c=2,
    detect_bc_ambiguity=True,     # B may be position OR company
    leads_layout=False,           # do not assume B=company
    col_phone=3, col_email=4, col_salesperson=5,
    col_att1=6, col_att2=7, col_att3=8,
    col_last_contacted=9, col_notes=10,
    country_hint="SA",
)

GULF_LEADS_SHEET_CONFIGS: Dict[str, WorkbookSheetConfig] = {
    cfg.sheet_name: cfg for cfg in [
        _LEADS_CONFIG, _SHEET16_CONFIG,
        _GHAIDA_FU, _AMIN_FU, _QUSAI, _DEMO_CONFIG,
        _OMAN, _OMAN_LEADS, _OMAN_LS, _OMAN_AMIN,
    ]
}

SKIP_SHEETS = {"Companies"}


# ── Companies tab reader ──────────────────────────────────────────────────────

def read_companies_tab(wb) -> FrozenSet[str]:
    """Return a frozenset of lowercased company names from the Companies sheet.

    Used by detect_company_position() to disambiguate B/C in Sheet16.
    """
    if "Companies" not in wb.sheetnames:
        return frozenset()
    ws = wb["Companies"]
    names: set[str] = set()
    for row in ws.iter_rows(min_row=1, values_only=True):
        if not row:
            continue
        for cell_val in row:
            if cell_val is not None:
                name = str(cell_val).strip()
                if name:
                    names.add(name.lower())
                break
    return frozenset(names)


# ── Cell extractor ────────────────────────────────────────────────────────────

def _cell(row_values: tuple, col_idx: Optional[int]) -> str:
    if col_idx is None or col_idx >= len(row_values):
        return ""
    val = row_values[col_idx]
    if val is None:
        return ""
    return str(val).strip()


def _count_attempt(raw: str) -> int:
    """Interpret attempt cell: numeric → count, non-empty text → 1, blank → 0."""
    if not raw:
        return 0
    try:
        v = int(float(raw))
        return max(0, v)
    except (ValueError, TypeError):
        return 1


# ── Single-sheet parser ────────────────────────────────────────────────────────

def parse_sheet(
    ws,
    config: WorkbookSheetConfig,
    companies_set: FrozenSet[str],
) -> List[LeadRow]:
    """Parse one openpyxl worksheet into a list of LeadRow objects.

    Guarantees:
    - Sheet16 row 1 (first data row) is NEVER skipped.
    - import_key is set on every valid row.
    - Rows lacking all of (name, normalised_phone, normalised_email) are marked
      invalid and excluded from import, but logged.
    """
    rows: List[LeadRow] = []
    data_start = 2 if config.has_header else 1

    for row_num, row_values in enumerate(
        ws.iter_rows(min_row=data_start, values_only=True), start=data_start
    ):
        # Skip completely empty rows
        if not row_values or all(
            v is None or (isinstance(v, str) and not v.strip())
            for v in row_values
        ):
            continue

        name_raw  = _cell(row_values, config.col_name)
        b_raw     = _cell(row_values, config.col_b)
        c_raw     = _cell(row_values, config.col_c)
        phone_raw = _cell(row_values, config.col_phone)
        email_raw = _cell(row_values, config.col_email)
        sp_raw    = _cell(row_values, config.col_salesperson) or config.default_salesperson
        att1_raw  = _cell(row_values, config.col_att1)
        att2_raw  = _cell(row_values, config.col_att2)
        att3_raw  = _cell(row_values, config.col_att3)
        last_ct   = _cell(row_values, config.col_last_contacted)
        notes_raw = _cell(row_values, config.col_notes)

        # Normalise identity fields
        norm_phone = normalize_phone(phone_raw, country_hint=config.country_hint)
        norm_email = normalize_email(email_raw)
        first_name, last_name = split_name(name_raw) if name_raw else ("", "")

        # Validity: must have at least one identity field
        if not first_name and not norm_phone and not norm_email:
            lr = LeadRow(
                source_sheet=config.sheet_name, source_row=row_num,
                is_invalid=True,
                invalid_reason="No name, phone, or email",
            )
            rows.append(lr)
            continue

        # Resolve B/C columns
        if config.detect_bc_ambiguity:
            position, company = detect_company_position(b_raw, c_raw, companies_set)
        elif config.leads_layout:
            # Standard Leads layout: B = company, C = position
            company  = b_raw or ""
            position = c_raw or ""
        else:
            company  = c_raw or ""
            position = b_raw or ""

        # Attempt count
        att1 = _count_attempt(att1_raw)
        att2 = _count_attempt(att2_raw)
        att3 = _count_attempt(att3_raw)
        attempt_count = min(att1 + att2 + att3, 3)

        # Status hint
        if config.is_demo_sheet:
            status_hint = "DEMO_SCHEDULED"
        elif not sp_raw:
            status_hint = "UNASSIGNED"
        elif attempt_count >= 2:
            status_hint = "NO_ANSWER"
        elif attempt_count == 1:
            status_hint = "CONTACTED"
        else:
            status_hint = "NEW"

        lr = LeadRow(
            first_name=first_name,
            last_name=last_name,
            company=company or "",
            position=position or "",
            phone=phone_raw,
            normalized_phone=norm_phone,
            email=email_raw,
            normalized_email=norm_email,
            notes=notes_raw,
            salesperson=sp_raw,
            attempt_1_text=att1_raw,
            attempt_2_text=att2_raw,
            attempt_3_text=att3_raw,
            attempt_count=attempt_count,
            last_contacted=last_ct or None,
            status_hint=status_hint,
            source_sheet=config.sheet_name,
            source_row=row_num,
            country_hint=config.country_hint,
        )
        lr.import_key = make_import_key(
            email=norm_email,
            phone=norm_phone,
            first_name=first_name,
            last_name=last_name,
            company=company or "",
        )
        rows.append(lr)

    return rows
