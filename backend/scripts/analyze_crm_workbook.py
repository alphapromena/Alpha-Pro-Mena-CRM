"""
Dry-run evaluation of the authoritative CRM workbook.

Reads the workbook and reports what it actually contains, with no database access
and no writes of any kind. Every number the migration relies on is derived here so
it can be checked before anything is imported, rather than trusting documented
counts.

Usage:
    python backend/scripts/analyze_crm_workbook.py "CRM data.xlsx" -o report.json

Identity rules follow the agreed priority, and deliberately refuse to guess:
  1. normalized email
  2. normalized phone + corroborating surname
  3. name + canonical company, only when both phone and email are missing

A phone shared by people with different names, or by rows owned by different
salespeople, is reported as ambiguous rather than merged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

# Sheet16 is headerless: physical row 1 is already a contact.
SHEET16 = "Sheet16"
SHEET16_HAS_HEADER = False
COL_NAME, COL_POSITION, COL_COMPANY, COL_PHONE, COL_EMAIL, COL_OWNER = 0, 1, 2, 3, 4, 5
COL_ATTEMPT_1, COL_ATTEMPT_2, COL_ATTEMPT_3 = 6, 7, 8

COMPANIES_SHEET = "Companies"
LEADS_SHEET = "Leads"
DEMO_SHEET = "Demo"
FOLLOWUP_SHEETS = ["Ghaida fu", "Amin fu"]

CANONICAL_OWNERS = {
    "saleh": "saleh@alphapromena.com",
    "hassan": "hassan@alphapromena.com",
    "amin": "amin@alphapromena.com",
    "ghaida": "ghaida@alphapromena.com",
    "qusai": "qusai@alphapromena.com",
    "aseel": "aseel@alphapromena.com",
    "abdallah": "abdallah@alphapromena.com",
}


# ─── normalisation ────────────────────────────────────────────────────────────

def norm_text(value: Any) -> str:
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", s).strip()


def norm_email(value: Any) -> str:
    s = norm_text(value).lower()
    if not s or "@" not in s:
        return ""
    # Guard against multiple addresses crammed into one cell.
    s = re.split(r"[;,/\s]+", s)[0]
    return s if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s) else ""


def norm_phone(value: Any) -> str:
    """Digits only, with a leading 00/+ collapsed. Empty when implausible."""
    s = norm_text(value)
    if not s:
        return ""
    digits = re.sub(r"\D", "", s)
    digits = re.sub(r"^00", "", digits)
    # Fewer than 7 digits cannot identify a person.
    return digits if len(digits) >= 7 else ""


def norm_company(value: Any) -> str:
    s = norm_text(value).lower()
    if not s:
        return ""
    s = s.replace("&", " and ")
    s = re.sub(r"[.,'`\"()\[\]]", " ", s)
    s = re.sub(
        r"\b(co|inc|ltd|llc|l\.l\.c|plc|corp|corporation|company|group|holding|holdings|wll|w\.l\.l|jsc|psc|sa|sal|est)\b",
        " ",
        s,
    )
    return re.sub(r"\s+", " ", s).strip()


def surname_key(name: Any) -> str:
    parts = norm_text(name).lower().split()
    return parts[-1] if parts else ""


def row_checksum(values: List[Any]) -> str:
    payload = "\x1f".join("" if v is None else str(v) for v in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_blank_row(values: Tuple[Any, ...]) -> bool:
    return all(norm_text(v) == "" for v in values)


# ─── Sheet16 ──────────────────────────────────────────────────────────────────

def analyse_sheet16(ws) -> Dict[str, Any]:
    rows = list(ws.iter_rows(values_only=True))
    start = 1 if SHEET16_HAS_HEADER else 0

    non_empty = 0
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    owner_source_counts: Counter = Counter()

    for idx in range(start, len(rows)):
        raw = rows[idx]
        row_no = idx + 1  # 1-based physical row
        if is_blank_row(raw):
            continue
        non_empty += 1

        name = norm_text(raw[COL_NAME]) if len(raw) > COL_NAME else ""
        company = norm_text(raw[COL_COMPANY]) if len(raw) > COL_COMPANY else ""
        phone = norm_phone(raw[COL_PHONE]) if len(raw) > COL_PHONE else ""
        email = norm_email(raw[COL_EMAIL]) if len(raw) > COL_EMAIL else ""
        owner_raw = norm_text(raw[COL_OWNER]) if len(raw) > COL_OWNER else ""
        owner_key = owner_raw.lower()

        owner_source_counts[owner_raw or "Unassigned"] += 1

        # A row identifies a person only if it has a name plus at least one way to
        # reach them, or a name plus a company.
        reasons = []
        if not name:
            reasons.append("missing name")
        if not (email or phone or company):
            reasons.append("no email, phone or company")
        if owner_key and owner_key not in CANONICAL_OWNERS:
            reasons.append(f"unknown salesperson '{owner_raw}'")

        record = {
            "source_row": row_no,
            "name": name,
            "position": norm_text(raw[COL_POSITION]) if len(raw) > COL_POSITION else "",
            "company": company,
            "company_key": norm_company(company),
            "phone": phone,
            "email": email,
            "owner_raw": owner_raw or "Unassigned",
            "owner_email": CANONICAL_OWNERS.get(owner_key),
            "row_checksum": row_checksum(list(raw)),
        }
        if reasons:
            invalid.append({**record, "reasons": reasons})
        else:
            valid.append(record)

    return {
        "physical_rows": len(rows),
        "has_header_row": SHEET16_HAS_HEADER,
        "non_empty_rows": non_empty,
        "valid_rows": len(valid),
        "invalid_rows": len(invalid),
        "invalid_row_numbers": [r["source_row"] for r in invalid],
        "invalid_detail": invalid[:50],
        "source_rows_by_salesperson": dict(owner_source_counts.most_common()),
        "_valid": valid,
    }


def deduplicate(valid: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Collapse rows that identify the same person. The first (lowest) source row wins
    so the outcome is deterministic; every collapse is explained.
    """
    canonical: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []

    by_email: Dict[str, int] = {}
    by_phone_surname: Dict[Tuple[str, str], int] = {}
    by_name_company: Dict[Tuple[str, str], int] = {}
    phone_owners: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for rec in valid:
        if rec["phone"]:
            phone_owners[rec["phone"]].append(rec)

    # A phone used by more than one surname, or across owners, cannot identify a
    # person on its own. Company switchboards look exactly like this.
    shared_phones = {
        p
        for p, recs in phone_owners.items()
        if len({surname_key(r["name"]) for r in recs}) > 1
        or len({r["owner_raw"] for r in recs}) > 1
    }

    for rec in valid:
        email, phone, name = rec["email"], rec["phone"], rec["name"]
        sk = surname_key(name)
        target: Optional[int] = None
        rule = None

        if email and email in by_email:
            target, rule = by_email[email], "email"
        elif phone and phone not in shared_phones and (phone, sk) in by_phone_surname:
            target, rule = by_phone_surname[(phone, sk)], "phone+surname"
        elif not email and not phone and rec["company_key"]:
            key = (name.lower(), rec["company_key"])
            if key in by_name_company:
                target, rule = by_name_company[key], "name+company"

        if target is not None:
            winner = canonical[target]
            duplicates.append({
                "duplicate_source_row": rec["source_row"],
                "winning_source_row": winner["source_row"],
                "rule": rule,
                "name": name,
                "email": email,
                "phone": phone,
                "company": rec["company"],
                "owner": rec["owner_raw"],
                "owner_conflict": rec["owner_raw"] != winner["owner_raw"],
                "reason": f"same person as row {winner['source_row']} by {rule}",
            })
            # Fill blanks on the winner without overwriting anything.
            for field in ("email", "phone", "company", "position"):
                if not winner.get(field) and rec.get(field):
                    winner[field] = rec[field]
            continue

        idx = len(canonical)
        canonical.append(dict(rec))
        if email:
            by_email.setdefault(email, idx)
        if phone and phone not in shared_phones:
            by_phone_surname.setdefault((phone, sk), idx)
        if not email and not phone and rec["company_key"]:
            by_name_company.setdefault((name.lower(), rec["company_key"]), idx)

    for phone in sorted(shared_phones):
        recs = phone_owners[phone]
        ambiguous.append({
            "phone": phone,
            "row_count": len(recs),
            "source_rows": [r["source_row"] for r in recs][:25],
            "distinct_names": sorted({r["name"] for r in recs})[:10],
            "distinct_owners": sorted({r["owner_raw"] for r in recs}),
            "reason": "phone shared across different people or owners; not merged",
        })

    return {
        "canonical_contacts": len(canonical),
        "duplicates_removed": len(duplicates),
        "duplicate_detail": duplicates,
        "canonical_by_salesperson": dict(Counter(r["owner_raw"] for r in canonical).most_common()),
        "ambiguous_shared_phones": len(ambiguous),
        "ambiguous_detail": ambiguous[:50],
        "_canonical": canonical,
    }


# ─── other sheets ─────────────────────────────────────────────────────────────

def analyse_companies(ws) -> Dict[str, Any]:
    rows = list(ws.iter_rows(values_only=True))
    header = [norm_text(v) for v in rows[0]] if rows else []
    source_rows = 0
    canonical: Dict[str, Dict[str, Any]] = {}
    collisions: List[Dict[str, Any]] = []
    invalid: List[int] = []

    for idx in range(1, len(rows)):
        raw = rows[idx]
        if is_blank_row(raw):
            continue
        source_rows += 1
        name = norm_text(raw[0])
        if not name:
            invalid.append(idx + 1)
            continue
        key = norm_company(name)
        if not key:
            invalid.append(idx + 1)
            continue
        if key in canonical:
            if canonical[key]["name"] != name:
                collisions.append({
                    "normalized_key": key,
                    "kept": canonical[key]["name"],
                    "kept_row": canonical[key]["source_row"],
                    "duplicate": name,
                    "duplicate_row": idx + 1,
                })
            canonical[key]["duplicate_rows"].append(idx + 1)
        else:
            canonical[key] = {"name": name, "source_row": idx + 1, "duplicate_rows": []}

    return {
        "header": header[:5],
        "source_rows": source_rows,
        "invalid_rows": len(invalid),
        "invalid_row_numbers": invalid[:50],
        "distinct_canonical_companies": len(canonical),
        "duplicates_collapsed": source_rows - len(canonical) - len(invalid),
        "collision_samples": collisions[:50],
        "_keys": set(canonical.keys()),
    }


def analyse_leads(ws) -> Dict[str, Any]:
    rows = list(ws.iter_rows(values_only=True))
    header = [norm_text(v) for v in rows[0]] if rows else []
    non_empty = sum(1 for idx in range(1, len(rows)) if not is_blank_row(rows[idx]))
    named_cols = [h for h in header if h]
    return {
        "physical_rows": len(rows),
        "header": header,
        "named_columns": len(named_cols),
        "total_columns": len(header),
        "non_empty_data_rows": non_empty,
    }


def analyse_activity(ws, label: str) -> Dict[str, Any]:
    rows = list(ws.iter_rows(values_only=True))
    header = [norm_text(v) for v in rows[0]] if rows else []
    non_empty = sum(1 for idx in range(1, len(rows)) if not is_blank_row(rows[idx]))
    return {
        "sheet": label,
        "physical_rows": len(rows),
        "header": header[:15],
        "non_empty_data_rows": non_empty,
    }


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Dry-run evaluation of the CRM workbook.")
    ap.add_argument("workbook")
    ap.add_argument("-o", "--out", default="crm_workbook_report.json")
    args = ap.parse_args()

    path = Path(args.workbook)
    if not path.exists():
        print(f"ERROR: workbook not found: {path}", file=sys.stderr)
        return 2

    wb = openpyxl.load_workbook(path, data_only=True)
    report: Dict[str, Any] = {
        "workbook": path.name,
        "source_file_checksum": file_checksum(path),
        "sheet_names": wb.sheetnames,
    }

    s16 = analyse_sheet16(wb[SHEET16])
    valid = s16.pop("_valid")
    dedup = deduplicate(valid)
    canonical = dedup.pop("_canonical")
    report["sheet16"] = {**s16, **dedup}

    comps = analyse_companies(wb[COMPANIES_SHEET])
    company_keys = comps.pop("_keys")
    report["companies"] = comps

    report["leads"] = analyse_leads(wb[LEADS_SHEET])

    activity = []
    if DEMO_SHEET in wb.sheetnames:
        activity.append(analyse_activity(wb[DEMO_SHEET], DEMO_SHEET))
    for name in FOLLOWUP_SHEETS:
        if name in wb.sheetnames:
            activity.append(analyse_activity(wb[name], name))
    report["historical_activity"] = activity

    # Linkage: which canonical contacts point at a company the master list knows.
    unlinked_company = [
        {"source_row": c["source_row"], "company": c["company"]}
        for c in canonical
        if c["company_key"] and c["company_key"] not in company_keys
    ]
    no_company = [c["source_row"] for c in canonical if not c["company_key"]]
    report["linkage"] = {
        "canonical_contacts": len(canonical),
        "contacts_with_company_not_in_master": len(unlinked_company),
        "contacts_with_no_company": len(no_company),
        "unlinked_company_samples": unlinked_company[:50],
    }

    report["ownership_summary"] = {
        "source_rows_by_salesperson": report["sheet16"]["source_rows_by_salesperson"],
        "canonical_by_salesperson": report["sheet16"]["canonical_by_salesperson"],
    }

    out = Path(args.out)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary, ASCII-safe for Windows terminals.
    s = report["sheet16"]
    print(f"workbook            : {report['workbook']}")
    print(f"sheets              : {len(report['sheet_names'])}")
    print(f"Sheet16 physical    : {s['physical_rows']}  (header row: {s['has_header_row']})")
    print(f"Sheet16 non-empty   : {s['non_empty_rows']}")
    print(f"Sheet16 valid       : {s['valid_rows']}")
    print(f"Sheet16 invalid     : {s['invalid_rows']} rows -> {s['invalid_row_numbers'][:10]}")
    print(f"canonical contacts  : {s['canonical_contacts']} (removed {s['duplicates_removed']} duplicates)")
    print(f"ambiguous phones    : {s['ambiguous_shared_phones']}")
    print("source rows by salesperson:")
    for k, v in s["source_rows_by_salesperson"].items():
        print(f"    {k:<12} {v}")
    print("canonical by salesperson:")
    for k, v in s["canonical_by_salesperson"].items():
        print(f"    {k:<12} {v}")
    c = report["companies"]
    print(f"Companies source    : {c['source_rows']} rows -> {c['distinct_canonical_companies']} distinct")
    l = report["leads"]
    print(f"Leads non-empty     : {l['non_empty_data_rows']} rows, {l['named_columns']}/{l['total_columns']} named cols")
    for a in activity:
        print(f"activity {a['sheet']:<10}: {a['non_empty_data_rows']} rows")
    print(f"unlinked companies  : {report['linkage']['contacts_with_company_not_in_master']}")
    print(f"report written      : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
