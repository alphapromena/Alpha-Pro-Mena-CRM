"""
tests/unit/test_gulf_import_reconciler.py

Unit tests for app.imports.reconciler.
Tests deduplication, row merging, DB matching, and record classification.
"""
import pytest
from app.imports.workbook_reader import LeadRow
from app.imports.reconciler import (
    CATEGORY_NEW,
    CATEGORY_MATCHED,
    CATEGORY_DUPLICATE,
    CATEGORY_INVALID,
    CATEGORY_AWAITING_REVIEW,
    DbSnapshot,
    ImportReport,
    _completeness_score,
    _merge_rows,
    _names_overlap,
    deduplicate,
    match_to_db,
    classify_rows,
)


def _make_row(**kwargs) -> LeadRow:
    defaults = {
        "source_sheet": "Leads",
        "source_row": 2,
        "first_name": "Saleh",
        "last_name": "Al-Ghamdi",
        "phone": "+966501234567",
        "normalized_phone": "+966501234567",
        "email": "saleh@example.com",
        "normalized_email": "saleh@example.com",
        "company": "Alpha Pro",
        "position": "Director",
        "salesperson": "Saleh",
        "import_key": "dummy_key_1",
    }
    defaults.update(kwargs)
    return LeadRow(**defaults)


# ── _completeness_score & _merge_rows ─────────────────────────────────────────

class TestRowMerge:
    def test_completeness_scoring(self):
        sparse = _make_row(email="", normalized_email="", position="", company="")
        rich = _make_row()
        assert _completeness_score(rich) > _completeness_score(sparse)

    def test_merge_preserves_richer_winner(self):
        row1 = _make_row(position="Manager", company="Alpha Pro", email="", normalized_email="")
        row2 = _make_row(position="", company="Alpha Pro", email="saleh@example.com", normalized_email="saleh@example.com")
        # row2 has email (score +10), row1 has position (+3) -> row2 should be winner, but position copied from row1
        merged = _merge_rows(row1, row2)
        assert merged.normalized_email == "saleh@example.com"
        assert merged.position == "Manager"
        assert merged.company == "Alpha Pro"

    def test_merge_takes_max_attempt_count(self):
        row1 = _make_row(attempt_count=1, attempt_1_text="Called no answer")
        row2 = _make_row(attempt_count=3, attempt_1_text="", attempt_2_text="Busy", attempt_3_text="Demo set")
        merged = _merge_rows(row1, row2)
        assert merged.attempt_count == 3
        assert merged.attempt_1_text == "Called no answer"
        assert merged.attempt_2_text == "Busy"
        assert merged.attempt_3_text == "Demo set"

    def test_merge_propagates_demo_scheduled(self):
        row1 = _make_row(status_hint="DEMO_SCHEDULED")
        row2 = _make_row(status_hint="NEW")
        merged = _merge_rows(row1, row2)
        assert merged.status_hint == "DEMO_SCHEDULED"


# ── deduplicate within batch ──────────────────────────────────────────────────

class TestDeduplicateBatch:
    def test_deduplicates_by_import_key(self):
        row1 = _make_row(import_key="key_abc", position="Sales")
        row2 = _make_row(import_key="key_abc", position="Sales Lead")
        unique, merged = deduplicate([row1, row2])
        assert len(unique) == 1
        assert merged == 1
        assert unique[0].import_key == "key_abc"

    def test_different_keys_not_merged(self):
        row1 = _make_row(import_key="key_1")
        row2 = _make_row(import_key="key_2")
        unique, merged = deduplicate([row1, row2])
        assert len(unique) == 2
        assert merged == 0

    def test_invalid_rows_pass_through(self):
        invalid_row = _make_row(is_invalid=True, import_key="", invalid_reason="Missing name")
        valid_row = _make_row(import_key="key_valid")
        unique, merged = deduplicate([invalid_row, valid_row])
        assert len(unique) == 2
        assert merged == 0


# ── _names_overlap ────────────────────────────────────────────────────────────

class TestNamesOverlap:
    def test_same_name(self):
        assert _names_overlap("Mohammed", "Mohammed") is True

    def test_partial_name(self):
        assert _names_overlap("Mohammed Ali", "Mohammed") is True

    def test_different_names(self):
        assert _names_overlap("Saleh", "Khaled") is False

    def test_empty_gives_benefit_of_doubt(self):
        assert _names_overlap("", "Khaled") is True
        assert _names_overlap("Saleh", "") is True


# ── match_to_db ───────────────────────────────────────────────────────────────

class TestMatchToDb:
    def test_match_by_import_key(self):
        snap = DbSnapshot(key_to_id={"k123": "contact_id_1"})
        row = _make_row(import_key="k123")
        cid, reason = match_to_db(row, snap)
        assert cid == "contact_id_1"
        assert reason == "key"

    def test_match_by_email_when_key_absent(self):
        snap = DbSnapshot(email_to_id={"user@test.com": "contact_id_2"})
        row = _make_row(import_key="unknown_key", normalized_email="user@test.com")
        cid, reason = match_to_db(row, snap)
        assert cid == "contact_id_2"
        assert reason == "email"

    def test_match_by_phone_with_name_corroboration(self):
        snap = DbSnapshot(phone_to_id={"+966501234567": ("contact_id_3", "Saleh")})
        row = _make_row(
            import_key="unknown",
            normalized_email="",
            normalized_phone="+966501234567",
            first_name="Saleh",
        )
        cid, reason = match_to_db(row, snap)
        assert cid == "contact_id_3"
        assert reason == "phone+name"

    def test_ambiguous_phone_same_number_different_name(self):
        snap = DbSnapshot(phone_to_id={"+966501234567": ("contact_id_3", "Ahmad")})
        row = _make_row(
            import_key="unknown",
            normalized_email="",
            normalized_phone="+966501234567",
            first_name="Khaled",
        )
        cid, reason = match_to_db(row, snap)
        assert cid is None
        assert reason == "phone_ambiguous"

    def test_no_match(self):
        snap = DbSnapshot()
        row = _make_row(import_key="new_key", normalized_email="new@example.com", normalized_phone="+966599999999")
        cid, reason = match_to_db(row, snap)
        assert cid is None
        assert reason == "none"


# ── classify_rows ─────────────────────────────────────────────────────────────

class TestClassifyRows:
    def test_classify_new_and_matched(self):
        snap = DbSnapshot(key_to_id={"key_existing": "c_100"})
        report = ImportReport()

        row_new = _make_row(import_key="key_new", source_sheet="Leads", source_row=2)
        row_matched = _make_row(import_key="key_existing", source_sheet="Leads", source_row=3)

        to_upsert, to_skip = classify_rows([row_new, row_matched], snap, report)

        assert len(to_upsert) == 2
        assert len(to_skip) == 0

        # Check matched vs new
        upsert_dict = {r.import_key: cid for r, cid in to_upsert}
        assert upsert_dict["key_new"] is None
        assert upsert_dict["key_existing"] == "c_100"

        assert report.per_sheet["Leads"].rows_new == 1
        assert report.per_sheet["Leads"].rows_matched_db == 1
        assert report.total_rows_read == 2

    def test_classify_invalid_row(self):
        snap = DbSnapshot()
        report = ImportReport()
        row_invalid = _make_row(
            is_invalid=True,
            invalid_reason="Col A is empty",
            source_sheet="Sheet16",
            source_row=67,
        )

        to_upsert, to_skip = classify_rows([row_invalid], snap, report)
        assert len(to_upsert) == 0
        assert len(to_skip) == 1
        assert report.total_invalid == 1
        assert len(report.invalid_rows) == 1
        assert report.invalid_rows[0]["sheet"] == "Sheet16"
        assert report.invalid_rows[0]["row"] == 67

    def test_legacy_salesperson_awaiting_review(self):
        snap = DbSnapshot()
        report = ImportReport()
        row_maria = _make_row(
            salesperson="Maria",
            import_key="maria_lead_1",
            source_sheet="Leads",
            source_row=10,
        )

        to_upsert, to_skip = classify_rows([row_maria], snap, report)
        assert len(to_upsert) == 1
        assert row_maria.status_hint == "UNASSIGNED"
        assert report.total_awaiting_review == 1
        assert len(report.awaiting_review_rows) == 1
        assert "Maria" in report.awaiting_review_rows[0]["salesperson"]

    def test_ambiguous_phone_conflict_logging(self):
        snap = DbSnapshot(phone_to_id={"+966501234567": ("cid_1", "Fatima")})
        report = ImportReport()
        row_conflict = _make_row(
            import_key="new_key",
            normalized_email="",
            normalized_phone="+966501234567",
            first_name="Omar",
            source_sheet="Leads",
            source_row=15,
        )

        to_upsert, to_skip = classify_rows([row_conflict], snap, report)
        assert report.total_conflicts == 1
        assert len(report.conflict_rows) == 1
        assert report.conflict_rows[0]["name"] == "Omar Al-Ghamdi"
