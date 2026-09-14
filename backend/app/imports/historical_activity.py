"""
Parse historical demos and follow-ups out of the workbook's activity sheets.

The activity sheets share Sheet16's column layout: name, company, position,
phone, email, salesperson, then several outcome columns.

  Demo       column G holds "DEMO at 04/june/2026" and column I holds the note
  Ghaida fu  outcome columns hold call results, not dated demos
  Amin fu    same shape as Ghaida fu

Dates are the dangerous part. A missing date is left as None and the row is
reported as missing-date. It is never replaced with today, which would silently
invent history and make an unattended call look like it happened this morning.

Idempotency is by (file checksum, worksheet, source row, activity type, row
checksum), so re-uploading the same workbook changes nothing, while a genuinely
edited row is recognised as different.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEMO_SHEET = "Demo"
FOLLOWUP_SHEETS = ("Ghaida fu", "Amin fu")

ACTIVITY_DEMO = "DEMO"
ACTIVITY_FOLLOWUP = "FOLLOW_UP"

COL_NAME, COL_COMPANY, COL_POSITION, COL_PHONE, COL_EMAIL, COL_OWNER = 0, 1, 2, 3, 4, 5
# Everything from here on is outcome / note material.
COL_OUTCOME_START = 6

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# Excel's day 1 is 1900-01-01, and it wrongly believes 1900 was a leap year, so
# the usual epoch offset of 1899-12-30 absorbs both facts.
EXCEL_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def parse_excel_date(value: Any) -> Optional[datetime]:
    """
    Best-effort date from a spreadsheet cell.

    Returns None rather than guessing. Callers must treat None as "no date on
    record", never as "now".
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    # Excel serial. Bounded to a sane window so a phone number or a small integer
    # is not read as a date.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20000 <= float(value) <= 60000:
            return EXCEL_EPOCH + timedelta(days=float(value))
        return None

    text = norm(value)
    if not text:
        return None

    # "DEMO at 04/june/2026", "Demo on 4 June 2026", "meeting 2026-06-04"
    text = re.sub(r"^\s*(demo|meeting|call|f/?u|follow[- ]?up)\s*(at|on|:)?\s*", "", text, flags=re.I)
    text = text.strip(" .,-")
    if not text:
        return None

    # 4/june/2026 or 04-Jun-26
    m = re.search(r"\b(\d{1,2})\s*[/\-. ]\s*([A-Za-z]{3,9})\s*[/\-. ]\s*(\d{2,4})\b", text)
    if m:
        day, mon, year = int(m.group(1)), MONTHS.get(m.group(2).lower()), int(m.group(3))
        if mon:
            return _build(year, mon, day)

    # 2026-06-04
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        return _build(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 04/06/2026, read day-first as the sheets are Gulf-authored
    m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b", text)
    if m:
        return _build(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    # "4 June 2026" or "June 4, 2026"
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b", text)
    if m and MONTHS.get(m.group(2).lower()):
        return _build(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b", text)
    if m and MONTHS.get(m.group(1).lower()):
        return _build(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))

    return None


def _build(year: int, month: int, day: int) -> Optional[datetime]:
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def row_sha(values: Sequence[Any]) -> str:
    payload = "\x1f".join("" if v is None else str(v) for v in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ActivityRow:
    """One parsed activity, with everything needed to place and de-duplicate it."""

    sheet: str
    source_row: int
    activity_type: str
    name: str = ""
    company: str = ""
    position: str = ""
    phone: str = ""
    email: str = ""
    owner_raw: str = ""
    activity_date: Optional[datetime] = None
    outcome: str = ""
    notes: str = ""
    next_step: str = ""
    row_checksum: str = ""
    problems: List[str] = field(default_factory=list)

    @property
    def is_importable(self) -> bool:
        """A row needs someone to attach to and something to say."""
        return bool(self.name) and "no identity" not in self.problems

    @property
    def missing_date(self) -> bool:
        return self.activity_date is None


def _looks_like_section_label(raw: Sequence[Any]) -> bool:
    """A lone value in column A with nothing beside it is a section heading."""
    filled = [i for i, v in enumerate(raw) if norm(v)]
    return filled == [COL_NAME]


def parse_activity_sheet(ws, sheet_name: str, activity_type: str) -> List[ActivityRow]:
    rows: List[ActivityRow] = []
    for idx, raw in enumerate(ws.iter_rows(values_only=True), start=1):
        if raw is None or all(norm(v) == "" for v in raw):
            continue
        if _looks_like_section_label(raw):
            continue

        def cell(i: int) -> str:
            return norm(raw[i]) if len(raw) > i else ""

        outcomes = [norm(raw[i]) for i in range(COL_OUTCOME_START, len(raw)) if norm(raw[i])]

        activity_date = None
        for value in list(raw[COL_OUTCOME_START:]):
            activity_date = parse_excel_date(value)
            if activity_date:
                break

        # The first outcome cell is the result; the rest read as commentary. Keeping
        # them apart lets the UI show a status without losing the free text.
        outcome = outcomes[0] if outcomes else ""
        notes = " | ".join(outcomes[1:]) if len(outcomes) > 1 else ""

        row = ActivityRow(
            sheet=sheet_name,
            source_row=idx,
            activity_type=activity_type,
            name=cell(COL_NAME),
            company=cell(COL_COMPANY),
            position=cell(COL_POSITION),
            phone=cell(COL_PHONE),
            email=cell(COL_EMAIL),
            owner_raw=cell(COL_OWNER),
            activity_date=activity_date,
            outcome=outcome,
            notes=notes,
            next_step=outcomes[-1] if len(outcomes) > 2 else "",
            row_checksum=row_sha(raw),
        )

        if not row.name:
            row.problems.append("no identity")
        if not (row.email or row.phone):
            row.problems.append("no email or phone to match on")
        if row.activity_date is None:
            # Recorded, never invented. A demo with no date stays undated.
            row.problems.append("missing date")
        if not row.owner_raw:
            row.problems.append("no salesperson")

        rows.append(row)
    return rows


def parse_workbook(wb, checksum: str) -> Dict[str, Any]:
    """Parse every supported activity sheet present in the workbook."""
    found: List[ActivityRow] = []
    sheets: List[Dict[str, Any]] = []

    for name, kind in [(DEMO_SHEET, ACTIVITY_DEMO)] + [(s, ACTIVITY_FOLLOWUP) for s in FOLLOWUP_SHEETS]:
        if name not in wb.sheetnames:
            continue
        parsed = parse_activity_sheet(wb[name], name, kind)
        found.extend(parsed)
        sheets.append({
            "sheet": name,
            "activity_type": kind,
            "rows": len(parsed),
            "importable": sum(1 for r in parsed if r.is_importable),
            "missing_date": sum(1 for r in parsed if r.missing_date),
        })

    return {
        "source_file_checksum": checksum,
        "sheets": sheets,
        "rows": found,
        "totals": {
            "rows": len(found),
            "importable": sum(1 for r in found if r.is_importable),
            "missing_date": sum(1 for r in found if r.missing_date),
            "demos": sum(1 for r in found if r.activity_type == ACTIVITY_DEMO),
            "follow_ups": sum(1 for r in found if r.activity_type == ACTIVITY_FOLLOWUP),
        },
    }


def dedupe_key(checksum: str, row: ActivityRow) -> str:
    """
    Stable identity for one imported activity.

    Includes the row checksum so an edited row is a new activity rather than a
    silent no-op, and the activity type so a demo and a follow-up parsed from the
    same physical row never collide.
    """
    return hashlib.sha256(
        "|".join([checksum, row.sheet, str(row.source_row), row.activity_type, row.row_checksum])
        .encode("utf-8")
    ).hexdigest()
