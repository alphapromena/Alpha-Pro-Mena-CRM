"""
Identity matching for contact imports.

The bug these cover: the importer built email and phone lookup keys and then only
ever looked records up by import_key. Since import_key embeds the phone, a change
in phone formatting between imports produced a different key, the same person was
treated as new, and the previous record was left behind.
"""
import pytest

from app.imports.identity import (
    MATCH_EMAIL,
    MATCH_NAME_COMPANY,
    MATCH_PHONE_SURNAME,
    ContactIndex,
    Identity,
    deduplicate,
    find_ambiguous_phones,
    norm_company,
    norm_email,
    norm_phone,
)


# ─── normalisation ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        (" +966 59 439 0699", "966594390699"),
        ("+966-59-439-0699", "966594390699"),
        ("00966594390699", "966594390699"),
        ("966594390699", "966594390699"),
        ("  ", ""),
        (None, ""),
        ("12345", ""),          # too short to identify anyone
        ("ext. 401", ""),
    ],
)
def test_phone_normalisation_survives_formatting(raw, expected):
    """The formatting differences that used to break import_key must not matter."""
    assert norm_phone(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  Ralhammad@STCBank.com.sa ", "ralhammad@stcbank.com.sa"),
        ("a@b.co; c@d.co", "a@b.co"),
        ("not-an-email", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_email_normalisation(raw, expected):
    assert norm_email(raw) == expected


def test_company_normalisation_collapses_legal_suffixes():
    assert norm_company("Malomatia  L.L.C.") == norm_company("malomatia llc")
    assert norm_company("STC Bank") == "stc bank"
    assert norm_company("A & B Holdings") == norm_company("A and B")


# ─── the regression: reformatted phone must still match ───────────────────────

def test_same_person_matches_after_phone_reformatting():
    index = ContactIndex()
    existing = {"id": "c1"}
    index.add(Identity.build(name="Ayman Ali", phone="+966 59 439 0699"), existing)

    incoming = Identity.build(name="Ayman Ali", phone="00966-59-439-0699")
    hit, rule = index.match(incoming)

    assert hit is existing, "reformatted phone must resolve to the same person"
    assert rule == MATCH_PHONE_SURNAME


def test_email_match_wins_over_everything():
    index = ContactIndex()
    by_email = {"id": "c1"}
    index.add(Identity.build(name="R Alhammad", email="ralhammad@stcbank.com.sa"), by_email)

    hit, rule = index.match(
        Identity.build(name="Completely Different", email="RALHAMMAD@stcbank.com.sa")
    )
    assert hit is by_email
    assert rule == MATCH_EMAIL


def test_a_record_is_findable_by_every_one_of_its_keys():
    """
    The old code used an if/elif chain, so a record registered under one key could
    never be found by another.
    """
    index = ContactIndex()
    rec = {"id": "c1"}
    index.add(
        Identity.build(name="Layla Alnisif", email="layla@malomatia.com",
                       phone="+974 4499 2888", company="Malomatia"),
        rec,
    )

    by_email, _ = index.match(Identity.build(name="Layla Alnisif", email="layla@malomatia.com"))
    by_phone, _ = index.match(Identity.build(name="Layla Alnisif", phone="9744499 2888"))

    assert by_email is rec
    assert by_phone is rec


# ─── name + company, only as a last resort ────────────────────────────────────

def test_name_and_company_match_when_no_phone_or_email():
    index = ContactIndex()
    rec = {"id": "c1"}
    index.add(Identity.build(name="Sara Q", company="Malomatia LLC"), rec)

    hit, rule = index.match(Identity.build(name="sara q", company="malomatia"))
    assert hit is rec
    assert rule == MATCH_NAME_COMPANY


def test_name_and_company_is_not_used_when_a_phone_is_present():
    """
    A phone that fails to match is a signal these may be different people. Falling
    back to name+company there would merge two colleagues with the same name.
    """
    index = ContactIndex()
    index.add(Identity.build(name="Sara Q", company="Malomatia"), {"id": "c1"})

    hit, rule = index.match(
        Identity.build(name="Sara Q", company="Malomatia", phone="+974 1111 2222")
    )
    assert hit is None
    assert rule is None


# ─── shared phones must never merge people ────────────────────────────────────

def test_switchboard_number_is_flagged_ambiguous():
    identities = [
        Identity.build(name="Ayman Ali", phone="+966 11 000 0000"),
        Identity.build(name="Nora Saleh", phone="966110000000"),
        Identity.build(name="Unique Person", phone="+966 55 123 4567"),
    ]
    ambiguous = find_ambiguous_phones(identities)

    assert "966110000000" in ambiguous
    assert "966551234567" not in ambiguous


def test_an_ambiguous_phone_never_produces_a_match():
    index = ContactIndex(ambiguous_phones={"966110000000"})
    index.add(Identity.build(name="Ayman Ali", phone="966110000000"), {"id": "c1"})

    hit, rule = index.match(Identity.build(name="Ayman Ali", phone="+966 11 000 0000"))
    assert hit is None, "a shared switchboard must not identify a person"
    assert rule is None


def test_index_learns_a_phone_is_shared_as_records_are_added():
    index = ContactIndex()
    index.add(Identity.build(name="Ayman Ali", phone="966110000000"), {"id": "c1"})
    index.add(Identity.build(name="Nora Saleh", phone="966110000000"), {"id": "c2"})

    assert "966110000000" in index.ambiguous_phones
    hit, _ = index.match(Identity.build(name="Ayman Ali", phone="966110000000"))
    assert hit is None


def test_same_surname_on_one_number_is_not_ambiguous():
    """A household or a direct line reused by one person stays matchable."""
    identities = [
        Identity.build(name="Ayman Ali", phone="966594390699"),
        Identity.build(name="A. Ali", phone="+966 59 439 0699"),
    ]
    assert find_ambiguous_phones(identities) == set()


# ─── deduplication of an incoming batch ───────────────────────────────────────

def test_deduplicate_collapses_by_email_and_keeps_the_first_row():
    rows = [
        (Identity.build(name="Ayman Ali", email="ayman@stc.com"), {"row": 1}),
        (Identity.build(name="Ayman A", email="AYMAN@stc.com"), {"row": 40}),
        (Identity.build(name="Other", email="other@stc.com"), {"row": 41}),
    ]
    canonical, duplicates, _ = deduplicate(rows)

    assert [p["row"] for _, p in canonical] == [1, 41]
    assert len(duplicates) == 1
    assert duplicates[0]["duplicate"]["row"] == 40
    assert duplicates[0]["winner"]["row"] == 1
    assert duplicates[0]["rule"] == MATCH_EMAIL


def test_deduplicate_does_not_merge_a_shared_switchboard():
    rows = [
        (Identity.build(name="Ayman Ali", phone="966110000000"), {"row": 1}),
        (Identity.build(name="Nora Saleh", phone="966110000000"), {"row": 2}),
    ]
    canonical, duplicates, ambiguous = deduplicate(rows)

    assert len(canonical) == 2, "different people on one switchboard stay separate"
    assert duplicates == []
    assert "966110000000" in ambiguous


def test_unresolvable_rows_are_kept_not_silently_dropped():
    rows = [(Identity.build(name="", email="", phone=""), {"row": 67})]
    canonical, duplicates, _ = deduplicate(rows)

    assert len(canonical) == 1
    assert duplicates == []


def test_deduplicate_is_stable_across_runs():
    rows = [
        (Identity.build(name="A B", phone="966594390699"), {"row": 5}),
        (Identity.build(name="A B", phone="+966 59 439 0699"), {"row": 9}),
    ]
    first = [p["row"] for _, p in deduplicate(rows)[0]]
    second = [p["row"] for _, p in deduplicate(rows)[0]]
    assert first == second == [5]
