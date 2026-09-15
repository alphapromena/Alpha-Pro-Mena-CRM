"""
Deterministic identity matching for contact imports.

Replaces the previous behaviour, which built ``email:`` and ``phone:`` lookup keys
and then only ever looked records up by ``import_key``. Because ``import_key``
embeds the phone number, any change in phone formatting between two imports
produced a different key, so the same person was treated as new and the previous
record was left behind. That is how a re-import can lose people.

Match priority, highest confidence first:

  1. normalized email
  2. normalized phone plus a corroborating surname
  3. name plus canonical company, and only when both phone and email are missing

A phone number on its own never merges two records. Company switchboards are shared
by many people, so a bare phone match would silently fuse unrelated contacts. Any
number seen against more than one surname is marked ambiguous and excluded from
matching entirely; those rows are reported instead.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

MATCH_EMAIL = "email"
MATCH_PHONE_SURNAME = "phone+surname"
MATCH_NAME_COMPANY = "name+company"

# Ordered best-first, so callers can reason about confidence.
MATCH_RULES = (MATCH_EMAIL, MATCH_PHONE_SURNAME, MATCH_NAME_COMPANY)


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def norm_email(value: Any) -> str:
    s = norm_text(value).lower()
    if not s or "@" not in s:
        return ""
    s = re.split(r"[;,/\s]+", s)[0]
    return s if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s) else ""


def norm_phone(value: Any) -> str:
    """
    Digits only, leading international prefix collapsed.

    Returns empty for anything under 7 digits, which cannot identify a person and
    would otherwise collide wildly (extensions, partial numbers, stray codes).
    """
    s = norm_text(value)
    if not s:
        return ""
    digits = re.sub(r"\D", "", s)
    digits = re.sub(r"^00", "", digits)
    return digits if len(digits) >= 7 else ""


def norm_company(value: Any) -> str:
    s = norm_text(value).lower()
    if not s:
        return ""
    s = s.replace("&", " and ")
    # Drop dots without inserting a space first, so a dotted abbreviation such as
    # "L.L.C." becomes "llc" and is recognised, rather than "l l c" which is not.
    s = s.replace(".", "")
    s = re.sub(r"[,'`\"()\[\]]", " ", s)
    s = re.sub(
        r"\b(co|inc|ltd|llc|plc|corp|corporation|company|group|holding|holdings"
        r"|wll|jsc|psc|sal|est)\b",
        " ",
        s,
    )
    return re.sub(r"\s+", " ", s).strip()


def surname_of(full_name: Any) -> str:
    parts = norm_text(full_name).lower().split()
    return parts[-1] if parts else ""


@dataclass(frozen=True)
class Identity:
    """The identifying facts of one person, already normalized."""

    email: str = ""
    phone: str = ""
    name: str = ""
    company_key: str = ""

    @classmethod
    def build(cls, *, email: Any = None, phone: Any = None, name: Any = None,
              company: Any = None) -> "Identity":
        return cls(
            email=norm_email(email),
            phone=norm_phone(phone),
            name=norm_text(name),
            company_key=norm_company(company),
        )

    @property
    def surname(self) -> str:
        return surname_of(self.name)

    @property
    def is_resolvable(self) -> bool:
        """False when there is nothing to match on at all."""
        return bool(self.email or self.phone or (self.name and self.company_key))


def find_ambiguous_phones(identities: Iterable[Identity]) -> Set[str]:
    """
    Phones that appear against more than one surname.

    These are switchboards and shared desk lines. Matching on them would merge
    different people, so they are excluded from phone matching and surfaced.
    """
    by_phone: Dict[str, Set[str]] = defaultdict(set)
    for ident in identities:
        if ident.phone:
            by_phone[ident.phone].add(ident.surname)
    return {phone for phone, surnames in by_phone.items() if len(surnames) > 1}


class ContactIndex:
    """
    Lookup over existing records, honouring the match priority.

    Records are duck-typed: anything with the attributes read by ``key_for`` works,
    which keeps this testable without a database.
    """

    def __init__(self, ambiguous_phones: Optional[Set[str]] = None) -> None:
        self._by_email: Dict[str, Any] = {}
        self._by_phone_surname: Dict[Tuple[str, str], Any] = {}
        self._by_name_company: Dict[Tuple[str, str], Any] = {}
        self._phone_surnames: Dict[str, Set[str]] = defaultdict(set)
        self.ambiguous_phones: Set[str] = set(ambiguous_phones or ())

    def add(self, identity: Identity, record: Any) -> None:
        """
        Register one existing record under every key it can be found by.

        Deliberately not an if/elif chain. The previous implementation registered a
        record under its import_key *or* its email *or* its phone, so a record that
        had one key could never be found by another.
        """
        if identity.email:
            self._by_email.setdefault(identity.email, record)
        if identity.phone:
            self._phone_surnames[identity.phone].add(identity.surname)
            if len(self._phone_surnames[identity.phone]) > 1:
                # Two different people already share it: stop trusting it.
                self.ambiguous_phones.add(identity.phone)
            self._by_phone_surname.setdefault((identity.phone, identity.surname), record)
        if identity.name and identity.company_key:
            self._by_name_company.setdefault(
                (identity.name.lower(), identity.company_key), record
            )

    def add_many(self, pairs: Sequence[Tuple[Identity, Any]]) -> None:
        for identity, record in pairs:
            self.add(identity, record)

    def match(self, identity: Identity) -> Tuple[Optional[Any], Optional[str]]:
        """
        Return ``(record, rule)`` for the best match, or ``(None, None)``.

        Rules are tried best-first and the first hit wins, so the outcome does not
        depend on dictionary ordering.
        """
        if identity.email:
            hit = self._by_email.get(identity.email)
            if hit is not None:
                return hit, MATCH_EMAIL

        if identity.phone and identity.phone not in self.ambiguous_phones:
            hit = self._by_phone_surname.get((identity.phone, identity.surname))
            if hit is not None:
                return hit, MATCH_PHONE_SURNAME

        # Weakest rule, so it is allowed only when there is genuinely nothing better.
        if not identity.email and not identity.phone:
            if identity.name and identity.company_key:
                hit = self._by_name_company.get(
                    (identity.name.lower(), identity.company_key)
                )
                if hit is not None:
                    return hit, MATCH_NAME_COMPANY

        return None, None


def deduplicate(
    rows: Sequence[Tuple[Identity, Any]]
) -> Tuple[List[Tuple[Identity, Any]], List[Dict[str, Any]], Set[str]]:
    """
    Collapse incoming rows that describe the same person.

    Returns ``(canonical, duplicates, ambiguous_phones)``. The first occurrence wins
    so the result is stable, and every collapse records which rule joined the two
    rows so it can be audited rather than taken on trust.
    """
    identities = [ident for ident, _ in rows]
    ambiguous = find_ambiguous_phones(identities)

    index = ContactIndex(ambiguous_phones=set(ambiguous))
    canonical: List[Tuple[Identity, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    position: Dict[int, int] = {}

    for identity, payload in rows:
        if not identity.is_resolvable:
            canonical.append((identity, payload))
            continue

        hit, rule = index.match(identity)
        if hit is not None:
            winner_identity, winner_payload = canonical[position[id(hit)]]
            duplicates.append({
                "rule": rule,
                "duplicate": payload,
                "winner": winner_payload,
                "email": identity.email,
                "phone": identity.phone,
                "name": identity.name,
            })
            continue

        marker = object()
        canonical.append((identity, payload))
        position[id(marker)] = len(canonical) - 1
        index.add(identity, marker)

    return canonical, duplicates, ambiguous
