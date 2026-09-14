"""
Reconcile the active contact set against Sheet16, without creating duplicates.

Sheet16 is the authoritative list of who is an active contact. This script makes
the database agree with it while preserving identity and history:

  * a Sheet16 row that matches an existing contact updates that contact in place,
    keeping its id, its status, and every call, note, demo and follow-up hanging
    off it
  * a Sheet16 row that matches nothing is inserted
  * an active contact that Sheet16 does not mention is retired, never deleted

Matching uses app.imports.identity, which resolves by email, then phone plus a
corroborating surname, then name plus company when there is no phone or email.
A phone shared by two different surnames is treated as a switchboard and never
merges anyone. This is the part that prevents duplicates: the previous importer
looked records up by import_key alone, and because import_key embeds the phone,
a reformatted number produced a new contact instead of finding the existing one.

Safety:
  * dry run by default; --execute is required to write
  * one transaction, so a failure leaves the database untouched
  * retirement is a soft delete, so foreign keys and history survive
  * idempotent: running twice changes nothing the second time
  * the workbook checksum is recorded on every row it touches

    python backend/scripts/reconcile_sheet16_contacts.py "CRM data.xlsx" --dsn ...
    python backend/scripts/reconcile_sheet16_contacts.py "CRM data.xlsx" --dsn ... --execute
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl  # noqa: E402

from app.imports.identity import (  # noqa: E402
    ContactIndex,
    Identity,
    find_ambiguous_phones,
    norm_company,
    norm_email,
    norm_phone,
    norm_text,
)

SHEET = "Sheet16"
# Sheet16 is headerless: physical row 1 is already a contact.
COL_NAME, COL_POSITION, COL_COMPANY, COL_PHONE, COL_EMAIL, COL_OWNER = 0, 1, 2, 3, 4, 5

CANONICAL_OWNERS = {
    "saleh": "saleh@alphapromena.com",
    "hassan": "hassan@alphapromena.com",
    "hasan": "hassan@alphapromena.com",     # the misspelling seen in the sheet
    "amin": "amin@alphapromena.com",
    "ghaida": "ghaida@alphapromena.com",
    "qusai": "qusai@alphapromena.com",
    "aseel": "aseel@alphapromena.com",
    "abdallah": "abdallah@alphapromena.com",
}


def clean_dsn(dsn: str) -> str:
    return re.sub(r"[?&](sslmode|channel_binding|options)=[^&]*", "", dsn.strip())


def redact(dsn: str) -> str:
    m = re.search(r"@([^/?]+)", dsn)
    return f"host={m.group(1)}" if m else "host=<unknown>"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_name(full: str) -> Tuple[str, str]:
    parts = norm_text(full).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def read_sheet16(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (valid_rows, invalid_rows). Physical 1-based row numbers throughout."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[SHEET]
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []

    for idx, raw in enumerate(ws.iter_rows(values_only=True), start=1):
        if raw is None or all(norm_text(v) == "" for v in raw):
            continue

        def cell(i: int) -> str:
            return norm_text(raw[i]) if len(raw) > i else ""

        name = cell(COL_NAME)
        company = cell(COL_COMPANY)
        phone = norm_phone(raw[COL_PHONE] if len(raw) > COL_PHONE else None)
        email = norm_email(raw[COL_EMAIL] if len(raw) > COL_EMAIL else None)
        owner_raw = cell(COL_OWNER)

        reasons = []
        if not name:
            reasons.append("missing name")
        if not (email or phone or company):
            reasons.append("no email, phone or company")

        rec = {
            "source_row": idx,
            "name": name,
            "position": cell(COL_POSITION),
            "company": company,
            "company_key": norm_company(company),
            "phone": phone,
            "phone_raw": norm_text(raw[COL_PHONE] if len(raw) > COL_PHONE else ""),
            "email": email,
            "owner_raw": owner_raw,
            "owner_email": CANONICAL_OWNERS.get(owner_raw.lower()),
            "row_sha": hashlib.sha256(
                "\x1f".join("" if v is None else str(v) for v in raw).encode()
            ).hexdigest(),
        }
        (invalid if reasons else valid).append({**rec, "reasons": reasons} if reasons else rec)

    wb.close()
    return valid, invalid


def collapse_sheet_duplicates(rows: List[Dict[str, Any]]):
    """Collapse rows inside the sheet that describe the same person."""
    identities = [
        Identity.build(email=r["email"], phone=r["phone"], name=r["name"], company=r["company"])
        for r in rows
    ]
    ambiguous = find_ambiguous_phones(identities)
    index = ContactIndex(ambiguous_phones=set(ambiguous))

    canonical: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    handles: Dict[int, int] = {}

    for rec, ident in zip(rows, identities):
        hit, rule = index.match(ident)
        if hit is not None:
            winner = canonical[handles[id(hit)]]
            duplicates.append({
                "duplicate_row": rec["source_row"],
                "winning_row": winner["source_row"],
                "rule": rule,
                "name": rec["name"],
                "owner": rec["owner_raw"],
                "owner_conflict": rec["owner_raw"] != winner["owner_raw"],
            })
            # Enrich the winner from the loser without overwriting anything.
            for f in ("email", "phone", "phone_raw", "company", "company_key", "position"):
                if not winner.get(f) and rec.get(f):
                    winner[f] = rec[f]
            continue

        marker = object()
        rec["_identity"] = ident
        canonical.append(rec)
        handles[id(marker)] = len(canonical) - 1
        index.add(ident, marker)

    return canonical, duplicates, ambiguous


async def reconcile(dsn: str, workbook: Path, execute: bool) -> Dict[str, Any]:
    import asyncpg

    checksum = file_sha256(workbook)
    valid, invalid = read_sheet16(workbook)
    canonical, sheet_dupes, ambiguous = collapse_sheet_duplicates(valid)

    conn = await asyncpg.connect(clean_dsn(dsn), ssl="require", timeout=90)
    report: Dict[str, Any] = {
        "workbook": workbook.name,
        "workbook_sha256": checksum,
        "database": await conn.fetchval("select current_database()"),
        "host": redact(dsn),
        "executed": execute,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sheet16": {
            "valid_rows": len(valid),
            "invalid_rows": len(invalid),
            "invalid_row_numbers": [r["source_row"] for r in invalid],
            "canonical_after_dedup": len(canonical),
            "duplicates_collapsed": len(sheet_dupes),
            "ambiguous_shared_phones": len(ambiguous),
        },
    }

    owners = {
        r["email"]: r["id"]
        for r in await conn.fetch(
            "select id, email from users where deleted_at is null and email like '%@alphapromena.com'"
        )
    }
    report["owner_accounts_resolved"] = len(owners)

    companies = {
        norm_company(r["name"]): r["id"]
        for r in await conn.fetch("select id, name from companies where deleted_at is null")
        if r["name"]
    }

    existing = await conn.fetch(
        """select id, first_name, last_name, email, phone, company_id, status,
                  owner_id, deleted_at, source_sheet
             from contacts"""
    )
    company_names = {
        r["id"]: norm_company(r["name"])
        for r in await conn.fetch("select id, name from companies")
        if r["name"]
    }

    index = ContactIndex()
    by_id: Dict[Any, Any] = {}
    for row in existing:
        ident = Identity.build(
            email=row["email"],
            phone=row["phone"],
            name=f"{row['first_name'] or ''} {row['last_name'] or ''}",
            company=company_names.get(row["company_id"], ""),
        )
        marker = object()
        by_id[id(marker)] = row
        index.add(ident, marker)

    report["existing_contacts"] = {
        "total": len(existing),
        "active_before": sum(1 for r in existing if r["deleted_at"] is None),
    }

    matched_ids: set = set()
    plan = {"update": 0, "insert": 0, "retire": 0, "by_rule": Counter(), "owner_conflicts": []}
    unresolved_owner: List[int] = []

    to_update: List[Tuple[Any, Dict[str, Any]]] = []
    to_insert: List[Dict[str, Any]] = []

    for rec in canonical:
        owner_id = owners.get(rec["owner_email"]) if rec["owner_email"] else None
        if owner_id is None:
            unresolved_owner.append(rec["source_row"])

        hit, rule = index.match(rec["_identity"])
        if hit is not None:
            row = by_id[id(hit)]
            if row["id"] in matched_ids:
                # Two sheet rows resolved to one contact; the sheet-level collapse
                # already ran, so this is a genuine near-duplicate. Skip, do not
                # create a second contact.
                plan["by_rule"]["already_matched"] += 1
                continue
            matched_ids.add(row["id"])
            plan["update"] += 1
            plan["by_rule"][rule] += 1
            if owner_id and row["owner_id"] and row["owner_id"] != owner_id:
                plan["owner_conflicts"].append({
                    "contact_id": str(row["id"]),
                    "source_row": rec["source_row"],
                    "sheet_owner": rec["owner_email"],
                })
            to_update.append((row["id"], {**rec, "owner_id": owner_id}))
        else:
            plan["insert"] += 1
            to_insert.append({**rec, "owner_id": owner_id})

    retire = [r["id"] for r in existing if r["deleted_at"] is None and r["id"] not in matched_ids]
    plan["retire"] = len(retire)
    plan["by_rule"] = dict(plan["by_rule"])
    plan["unresolved_owner_rows"] = unresolved_owner[:50]
    plan["unresolved_owner_count"] = len(unresolved_owner)
    plan["owner_conflict_count"] = len(plan["owner_conflicts"])
    plan["owner_conflicts"] = plan["owner_conflicts"][:25]
    report["plan"] = plan
    report["projected_active_after"] = plan["update"] + plan["insert"]

    projected_owner = Counter()
    for rec in canonical:
        projected_owner[rec["owner_email"] or "UNASSIGNED"] += 1
    report["projected_active_by_owner"] = dict(projected_owner.most_common())

    if execute:
        tx = conn.transaction()
        await tx.start()
        try:
            now = datetime.now(timezone.utc)
            for contact_id, rec in to_update:
                first, last = split_name(rec["name"])
                await conn.execute(
                    """update contacts set
                         first_name = $2, last_name = $3,
                         position = coalesce(nullif($4,''), position),
                         email    = coalesce(nullif($5,''), email),
                         phone    = coalesce(nullif($6,''), phone),
                         company_id = coalesce($7, company_id),
                         owner_id = coalesce($8, owner_id),
                         source_sheet = 'Sheet16',
                         sheet_order = $9,
                         import_key = $10,
                         deleted_at = null,
                         archived_at = null,
                         updated_at = $11
                       where id = $1""",
                    contact_id, first, last, rec["position"], rec["email"], rec["phone_raw"],
                    companies.get(rec["company_key"]), rec["owner_id"], rec["source_row"],
                    f"{checksum[:12]}:{rec['source_row']}", now,
                )
            for rec in to_insert:
                first, last = split_name(rec["name"])
                await conn.execute(
                    # priority, is_dnc and attempt_count are NOT NULL with no database
                    # default, so they must be supplied explicitly on insert.
                    """insert into contacts
                         (id, first_name, last_name, position, email, phone, company_id,
                          owner_id, status, priority, is_dnc, attempt_count,
                          source, source_sheet, sheet_order, import_key,
                          created_at, updated_at)
                       values (gen_random_uuid(), $1,$2,$3,nullif($4,''),nullif($5,''),$6,$7,
                               'NEW','MEDIUM',false,0,'Sheet16','Sheet16',$8,$9,$10,$10)""",
                    first, last, rec["position"], rec["email"], rec["phone_raw"],
                    companies.get(rec["company_key"]), rec["owner_id"],
                    rec["source_row"], f"{checksum[:12]}:{rec['source_row']}", now,
                )
            if retire:
                # Soft retire only. The rows and every foreign key pointing at them
                # survive, so demos, calls and follow-ups keep their contact.
                await conn.execute(
                    """update contacts
                          set deleted_at = $2, archived_at = $2, updated_at = $2
                        where id = any($1::uuid[]) and deleted_at is null""",
                    retire, now,
                )
            await tx.commit()
        except Exception:
            await tx.rollback()
            await conn.close()
            raise

    report["actual_active_after"] = await conn.fetchval(
        "select count(*) from contacts where deleted_at is null"
    )
    report["actual_by_owner"] = {
        r["email"]: r["n"]
        for r in await conn.fetch(
            """select u.email, count(*) n from contacts c join users u on u.id = c.owner_id
                where c.deleted_at is null group by u.email order by n desc"""
        )
    }
    report["duplicate_check"] = {
        "same_email_twice": await conn.fetchval(
            """select count(*) from (select lower(email) e from contacts
                where deleted_at is null and email is not null and email <> ''
                group by 1 having count(*) > 1) x"""
        ),
    }
    await conn.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile active contacts against Sheet16.")
    ap.add_argument("workbook")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("-o", "--out", default="")
    args = ap.parse_args()

    if not args.dsn:
        print("ERROR: no connection string. Pass --dsn or set DATABASE_URL.", file=sys.stderr)
        return 2
    wb = Path(args.workbook)
    if not wb.exists():
        print(f"ERROR: workbook not found: {wb}", file=sys.stderr)
        return 2

    rep = asyncio.run(reconcile(args.dsn, wb, args.execute))
    s, p = rep["sheet16"], rep["plan"]

    print(f"{'EXECUTED' if rep['executed'] else 'DRY RUN (nothing written)'}   "
          f"db={rep['database']}  {rep['host']}")
    print(f"workbook {rep['workbook']}  sha256 {rep['workbook_sha256'][:16]}...")
    print()
    print(f"Sheet16 valid rows        : {s['valid_rows']}")
    print(f"  invalid                 : {s['invalid_rows']} -> rows {s['invalid_row_numbers'][:8]}")
    print(f"  collapsed in-sheet dupes: {s['duplicates_collapsed']}")
    print(f"  canonical contacts      : {s['canonical_after_dedup']}")
    print(f"  ambiguous shared phones : {s['ambiguous_shared_phones']} (never merged)")
    print()
    print(f"existing contacts         : {rep['existing_contacts']['total']} "
          f"({rep['existing_contacts']['active_before']} active before)")
    print(f"  matched -> update       : {p['update']}   by rule: {p['by_rule']}")
    print(f"  new     -> insert       : {p['insert']}")
    print(f"  not in Sheet16 -> retire: {p['retire']}")
    print(f"  owner conflicts         : {p['owner_conflict_count']}")
    print(f"  rows with no owner      : {p['unresolved_owner_count']}")
    print()
    print(f"projected active after    : {rep['projected_active_after']}")
    print("projected by owner:")
    for k, v in rep["projected_active_by_owner"].items():
        print(f"    {k:<34} {v}")
    print()
    print(f"actual active now         : {rep['actual_active_after']}")
    for k, v in rep["actual_by_owner"].items():
        print(f"    {k:<34} {v}")
    print(f"duplicate emails active   : {rep['duplicate_check']['same_email_twice']}")

    if args.out:
        Path(args.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nreport written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
