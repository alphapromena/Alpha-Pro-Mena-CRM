"""
Archive every non-empty row of the Leads worksheet.

Leads is history, not an active contact list. Its rows are preserved verbatim so
they can be searched and audited later, and they never become active contacts.

What each archived row keeps:

  * the worksheet name and the original 1-based physical row number
  * every source column, stored under its real header rather than col_0, col_1
  * the raw cell values, unmodified
  * the worksheet header itself, so raw_data stays readable years later
  * the sha256 of the workbook and of the row

Re-running with the same workbook inserts nothing. That is enforced in the
database by a unique index on (source_file_checksum, sheet_name, row_number),
not merely by a check in this script, so two concurrent runs cannot both win.

    python backend/scripts/archive_leads_worksheet.py "CRM data.xlsx" --dsn ...
    python backend/scripts/archive_leads_worksheet.py "CRM data.xlsx" --dsn ... --execute
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl  # noqa: E402

SHEET = "Leads"

# Widths of the typed convenience columns in leads_archive. raw_data always holds
# the complete, unmodified row, so trimming these for indexing loses nothing.
FIELD_WIDTHS = {
    "name": 255, "company_name": 255, "position": 255,
    "phone": 100, "email": 255, "salesperson": 100,
}
# Header labels seen in the Leads worksheet, mapped to the archive's typed columns.
FIELD_HINTS = {
    "name": ("name", "full name", "contact", "contact name"),
    "company_name": ("company", "company name", "account"),
    "position": ("position", "title", "job title"),
    "phone": ("phone", "mobile", "telephone", "contact number"),
    "email": ("email", "e-mail", "mail"),
    "salesperson": ("sales person", "salesperson", "owner", "assigned to"),
}


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


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


def map_headers(header: List[str]) -> Dict[str, int]:
    """Map the archive's typed columns onto whichever position the sheet uses."""
    found: Dict[str, int] = {}
    # The Leads sheet leaves column A unlabelled, but it holds the contact name.
    # Without this the name column is silently dropped from every archived row.
    if header and not norm(header[0]):
        found["name"] = 0
    for idx, label in enumerate(header):
        low = norm(label).lower()
        if not low:
            continue
        for field, hints in FIELD_HINTS.items():
            if field in found:
                continue
            if any(low == h or low.startswith(h) for h in hints):
                found[field] = idx
    return found


def read_leads(path: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[SHEET]
    rows = ws.iter_rows(values_only=True)

    raw_header = next(rows, None) or ()
    header = [norm(v) for v in raw_header]
    # Unnamed columns still carry data, so give them a stable positional label
    # rather than discarding the column entirely.
    labels = [h if h else f"column_{i + 1}" for i, h in enumerate(header)]
    pos = map_headers(header)

    out: List[Dict[str, Any]] = []
    for idx, raw in enumerate(rows, start=2):  # physical row numbers, header was row 1
        if raw is None or all(norm(v) == "" for v in raw):
            continue
        # Every column, under its real name, values untouched.
        cells = {
            labels[i] if i < len(labels) else f"column_{i + 1}":
                (None if raw[i] is None else str(raw[i]))
            for i in range(len(raw))
        }

        def at(field: str) -> Optional[str]:
            i = pos.get(field)
            if i is None or i >= len(raw):
                return None
            value = norm(raw[i])
            if not value:
                return None
            # Some cells hold prose where a phone or title belongs. Trim to the
            # column width rather than failing the whole archive; raw_data keeps
            # the original in full.
            limit = FIELD_WIDTHS.get(field)
            return value[:limit] if limit and len(value) > limit else value

        out.append({
            "row_number": idx,
            "raw_data": json.dumps(cells, ensure_ascii=False),
            "name": at("name"),
            "company_name": at("company_name"),
            "position": at("position"),
            "phone": at("phone"),
            "email": at("email"),
            "salesperson": at("salesperson"),
            "row_sha": hashlib.sha256(
                "\x1f".join("" if v is None else str(v) for v in raw).encode("utf-8")
            ).hexdigest(),
        })
    wb.close()
    return labels, out


async def run(dsn: str, workbook: Path, execute: bool, batch: str) -> Dict[str, Any]:
    import asyncpg

    checksum = file_sha256(workbook)
    labels, rows = read_leads(workbook)
    header_json = json.dumps(labels, ensure_ascii=False)

    conn = await asyncpg.connect(clean_dsn(dsn), ssl="require", timeout=90)
    report: Dict[str, Any] = {
        "workbook": workbook.name,
        "workbook_sha256": checksum,
        "database": await conn.fetchval("select current_database()"),
        "host": redact(dsn),
        "executed": execute,
        "batch_id": batch,
        "sheet": SHEET,
        "header": labels,
        "named_columns": sum(1 for l in labels if not l.startswith("column_")),
        "total_columns": len(labels),
        "non_empty_rows": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    cols = {
        r["column_name"]
        for r in await conn.fetch(
            "select column_name from information_schema.columns where table_name='leads_archive'"
        )
    }
    required = {"source_file_checksum", "header_json", "source_row_sha"}
    missing = sorted(required - cols)
    report["schema_ready"] = not missing
    if missing:
        report["missing_columns"] = missing
        report["hint"] = "run: alembic upgrade head  (revision a4d2c8b19e77)"
        await conn.close()
        return report

    already = await conn.fetchval(
        "select count(*) from leads_archive where source_file_checksum = $1", checksum
    )
    report["already_archived_for_this_file"] = already
    report["would_insert"] = 0 if already else len(rows)

    if execute and not already:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.executemany(
                """insert into leads_archive
                     (id, batch_id, sheet_name, row_number, raw_data, name, company_name,
                      position, phone, email, salesperson, row_checksum,
                      source_file_checksum, header_json, source_row_sha, archived_at)
                   values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                   on conflict (source_file_checksum, sheet_name, row_number)
                     where source_file_checksum is not null
                   do nothing""",
                [
                    (
                        uuid.uuid4(), batch, SHEET, r["row_number"], r["raw_data"],
                        r["name"], r["company_name"], r["position"], r["phone"],
                        r["email"], r["salesperson"], r["row_sha"],
                        checksum, header_json, r["row_sha"],
                        datetime.now(timezone.utc),
                    )
                    for r in rows
                ],
            )
            await tx.commit()
        except Exception:
            await tx.rollback()
            await conn.close()
            raise

    report["archived_total"] = await conn.fetchval("select count(*) from leads_archive")
    report["archived_this_file"] = await conn.fetchval(
        "select count(*) from leads_archive where source_file_checksum = $1", checksum
    )
    report["active_contacts_from_leads"] = await conn.fetchval(
        "select count(*) from contacts where deleted_at is null and source_sheet = 'Leads'"
    )
    await conn.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Archive the Leads worksheet.")
    ap.add_argument("workbook")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--batch", default=f"leads-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}")
    args = ap.parse_args()

    if not args.dsn:
        print("ERROR: no connection string. Pass --dsn or set DATABASE_URL.", file=sys.stderr)
        return 2
    wb = Path(args.workbook)
    if not wb.exists():
        print(f"ERROR: workbook not found: {wb}", file=sys.stderr)
        return 2

    rep = asyncio.run(run(args.dsn, wb, args.execute, args.batch))

    print(f"{'EXECUTED' if rep['executed'] else 'DRY RUN (nothing written)'}   "
          f"db={rep['database']}  {rep['host']}")
    print(f"workbook {rep['workbook']}  sha256 {rep['workbook_sha256'][:16]}...")
    if not rep["schema_ready"]:
        print(f"\nSCHEMA NOT READY. missing columns: {rep['missing_columns']}")
        print(f"  {rep['hint']}")
        return 1
    print(f"\nworksheet          : {rep['sheet']}")
    print(f"non-empty rows     : {rep['non_empty_rows']}")
    print(f"columns preserved  : {rep['total_columns']} ({rep['named_columns']} with real headers)")
    print(f"header             : {rep['header'][:8]}")
    print(f"already archived   : {rep['already_archived_for_this_file']} rows for this file")
    print(f"would insert       : {rep['would_insert']}")
    print(f"\narchive total now  : {rep['archived_total']}")
    print(f"  for this file    : {rep['archived_this_file']}")
    print(f"active contacts sourced from Leads: {rep['active_contacts_from_leads']} (must be 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
