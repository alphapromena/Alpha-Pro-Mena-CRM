"""
Parsing historical demos and follow-ups.

The rule that matters most: a missing date stays missing. Substituting today
would invent history and make an untouched row look like it happened this
morning, which is worse than an obvious gap.
"""
from datetime import date, datetime, timezone

import pytest

from app.imports.historical_activity import (
    ACTIVITY_DEMO,
    ACTIVITY_FOLLOWUP,
    ActivityRow,
    dedupe_key,
    parse_activity_sheet,
    parse_excel_date,
    row_sha,
)


# ─── dates ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("DEMO at 04/june/2026", (2026, 6, 4)),
        ("DEMO at 18/june/2026 ", (2026, 6, 18)),
        ("Demo on 4 June 2026", (2026, 6, 4)),
        ("June 4, 2026", (2026, 6, 4)),
        ("2026-06-04", (2026, 6, 4)),
        ("04/06/2026", (2026, 6, 4)),      # day-first, these sheets are Gulf-authored
        ("04-Jun-26", (2026, 6, 4)),
        ("meeting 2026-06-04", (2026, 6, 4)),
    ],
)
def test_parses_the_date_formats_the_sheets_actually_use(raw, expected):
    got = parse_excel_date(raw)
    assert got is not None, f"failed to parse {raw!r}"
    assert (got.year, got.month, got.day) == expected


def test_parses_a_real_datetime_and_date():
    assert parse_excel_date(datetime(2026, 6, 4)).day == 4
    assert parse_excel_date(date(2026, 6, 4)).month == 6


def test_parses_an_excel_serial_number():
    # 46177 is 2026-06-04 under Excel's epoch.
    got = parse_excel_date(46177)
    assert got is not None
    assert (got.year, got.month) == (2026, 6)


@pytest.mark.parametrize(
    "raw",
    [
        None, "", "   ", "No Answer", "Asked for email", "Re Call",
        "wrong number", "first week in aug", "TBD",
        966594390699,        # a phone number, not a serial
        5,                   # too small to be a date
        "الاتصال عن طريق الايميل",
    ],
)
def test_returns_none_rather_than_guessing(raw):
    """Anything that is not clearly a date must come back as no date at all."""
    assert parse_excel_date(raw) is None


def test_never_substitutes_today_for_a_missing_date():
    before = datetime.now(timezone.utc)
    got = parse_excel_date("No Answer")
    assert got is None, "a missing date must not become now()"
    assert not isinstance(got, datetime)
    assert before is not None  # the point: nothing derived from the clock


def test_an_impossible_date_is_rejected():
    assert parse_excel_date("31/february/2026") is None


# ─── sheet parsing ────────────────────────────────────────────────────────────

class FakeSheet:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


DEMO_ROWS = [
    (" Saleh",) + (None,) * 10,                       # a section heading, not data
    ("Qais Al-Nussirat", "NourNet", "Senior Manager", " +966 55 693 2540",
     "qais@nour.net.sa", "SALEH", "DEMO at 04/june/2026", "note one",
     "A follow-up email was sent", None, None),
    ("Hadeel Samaha", "Housing Bank", "Manager", " +962 7 9118 9404",
     "hsamaha@hbtf.com.jo", "SALEH", "DEMO at 08/june/2026", None,
     "A second meeting", None, None),
    ("No Date Person", "SomeCo", "Analyst", " +971 50 000 0000",
     "nd@someco.com", "SALEH", "No Answer", None, None, None, None),
]


def test_skips_a_section_heading_row():
    rows = parse_activity_sheet(FakeSheet(DEMO_ROWS), "Demo", ACTIVITY_DEMO)
    assert all(r.name != "Saleh" for r in rows)
    assert len(rows) == 3


def test_extracts_the_demo_date_and_keeps_the_note():
    rows = parse_activity_sheet(FakeSheet(DEMO_ROWS), "Demo", ACTIVITY_DEMO)
    qais = next(r for r in rows if r.name.startswith("Qais"))

    assert qais.activity_type == ACTIVITY_DEMO
    assert qais.activity_date is not None
    assert (qais.activity_date.year, qais.activity_date.month, qais.activity_date.day) == (2026, 6, 4)
    assert qais.company == "NourNet"
    assert qais.email == "qais@nour.net.sa"
    assert qais.owner_raw == "SALEH"
    assert "follow-up email" in qais.notes


def test_a_row_without_a_date_is_flagged_not_dated():
    rows = parse_activity_sheet(FakeSheet(DEMO_ROWS), "Demo", ACTIVITY_DEMO)
    undated = next(r for r in rows if r.name == "No Date Person")

    assert undated.activity_date is None
    assert undated.missing_date is True
    assert "missing date" in undated.problems
    # It is still importable; the date is simply unknown.
    assert undated.is_importable is True


def test_physical_row_numbers_are_preserved():
    rows = parse_activity_sheet(FakeSheet(DEMO_ROWS), "Demo", ACTIVITY_DEMO)
    assert [r.source_row for r in rows] == [2, 3, 4]


def test_follow_up_sheet_captures_outcomes_without_a_date():
    fu_rows = [
        ("Dhafer Alghamdi", "Saudi Paper", "IT Specialist", " +966 53 689 0155",
         "dhafer@saudipaper.com", "Ghaida", "Asked for email", "NOT THE RIGHT PERSON",
         None, "whatsapp note", None),
    ]
    rows = parse_activity_sheet(FakeSheet(fu_rows), "Ghaida fu", ACTIVITY_FOLLOWUP)
    r = rows[0]

    assert r.activity_type == ACTIVITY_FOLLOWUP
    assert r.outcome == "Asked for email"
    assert "NOT THE RIGHT PERSON" in r.notes
    assert r.activity_date is None
    assert r.is_importable is True


def test_a_row_with_no_name_is_not_importable():
    rows = parse_activity_sheet(
        FakeSheet([(None, "SomeCo", None, None, None, "Amin", "No Answer")]),
        "Amin fu", ACTIVITY_FOLLOWUP,
    )
    assert rows[0].is_importable is False
    assert "no identity" in rows[0].problems


def test_a_row_with_no_contact_details_is_reported():
    rows = parse_activity_sheet(
        FakeSheet([("Someone", "SomeCo", None, None, None, "Amin", "No Answer")]),
        "Amin fu", ACTIVITY_FOLLOWUP,
    )
    assert "no email or phone to match on" in rows[0].problems


# ─── idempotency ──────────────────────────────────────────────────────────────

def _row(**kw):
    base = dict(sheet="Demo", source_row=2, activity_type=ACTIVITY_DEMO,
                name="A", row_checksum=row_sha(("A", "B")))
    base.update(kw)
    return ActivityRow(**base)


def test_the_same_row_from_the_same_file_yields_the_same_key():
    a, b = _row(), _row()
    assert dedupe_key("filesha", a) == dedupe_key("filesha", b)


def test_an_edited_row_yields_a_different_key():
    original = _row(row_checksum=row_sha(("A", "B")))
    edited = _row(row_checksum=row_sha(("A", "CHANGED")))
    assert dedupe_key("filesha", original) != dedupe_key("filesha", edited)


def test_a_different_file_yields_a_different_key():
    assert dedupe_key("file-one", _row()) != dedupe_key("file-two", _row())


def test_demo_and_follow_up_from_one_row_do_not_collide():
    demo = _row(activity_type=ACTIVITY_DEMO)
    fu = _row(activity_type=ACTIVITY_FOLLOWUP)
    assert dedupe_key("filesha", demo) != dedupe_key("filesha", fu)


def test_different_sheets_do_not_collide():
    a = _row(sheet="Ghaida fu")
    b = _row(sheet="Amin fu")
    assert dedupe_key("filesha", a) != dedupe_key("filesha", b)
