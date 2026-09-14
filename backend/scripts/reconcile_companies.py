"""
Reconcile the active company list against the Companies worksheet.

The Companies worksheet is the master list. The database currently holds more
companies than the worksheet has distinct names, because previous imports created
a company per spelling variant and never collapsed them.

What this does:

  * collapses spelling variants onto one canonical company per normalized name
  * reassigns every foreign key from the losing company to the winner, so no
    contact, demo or opportunity is orphaned
  * soft-archives the losers, never deletes them
  * inserts companies the worksheet has and the database lacks
  * soft-archives active companies the worksheet does not mention

Normalization is Unicode NFKC, trimmed, repeated spaces collapsed, punctuation
and dotted abbreviations folded, common legal suffixes dropped, case-insensitive.
Two different names that normalize to the same key are reported as a collision
so a wrong merge is visible rather than silent.

    python backend/scripts/reconcile_companies.py "CRM data.xlsx" --dsn ...
    python backend/scripts/reconcile_companies.py "CRM data.xlsx" --dsn ... --execute
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl  # noqa: E402

from app.imports.identity import norm_company, norm_text  # noqa: E402

SHEET = "Companies"


def clean_dsn(dsn: str) -> str:
    return re.sub(r"[?&](sslmode|channel_binding|options)=[^&]*", "", dsn.strip())


def redact(dsn: str) -> str:
    m = re.search(r"@([^/?]+)", dsn)
    return f"host={m.group(1)}" if m else "host=<unknown>"


def read_companies(path: Path) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], int, List[int]]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[SHEET]
    rows = ws.iter_rows(values_only=True)
    next(rows, None)  # header row

    canonical: Dict[str, Dict[str, Any]] = {}
    collisions: List[Dict[str, Any]] = []
    invalid: List[int] = []
    source_rows = 0

    for idx, raw in enumerate(rows, start=2):
        if raw is None or all(norm_text(v) == "" for v in raw):
            continue
        source_rows += 1
        name = norm_text(raw[0]) if raw else ""
        key = norm_company(name)
        if not name or not key:
            invalid.append(idx)
            continue
        if key in canonical:
            if canonical[key]["name"].lower() != name.lower():
                collisions.append({
                    "key": key,
                    "kept": canonical[key]["name"],
                    "kept_row": canonical[key]["row"],
                    "also": name,
                    "also_row": idx,
                })
        else:
            canonical[key] = {"name": name, "row": idx}
    wb.close()
    return canonical, collisions, source_rows, invalid


async def run(dsn: str, workbook: Path, execute: bool) -> Dict[str, Any]:
    import asyncpg

    canonical, collisions, source_rows, invalid = read_companies(workbook)

    conn = await asyncpg.connect(clean_dsn(dsn), ssl="require", timeout=120)
    report: Dict[str, Any] = {
        "workbook": workbook.name,
        "database": await conn.fetchval("select current_database()"),
        "host": redact(dsn),
        "executed": execute,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "worksheet": {
            "source_rows": source_rows,
            "invalid_rows": len(invalid),
            "distinct_companies": len(canonical),
            "name_collisions": len(collisions),
            "collision_samples": collisions[:20],
        },
    }

    fks = [
        (r["tbl"], r["col"])
        for r in await conn.fetch("""
            select tc.table_name tbl, kcu.column_name col
              from information_schema.table_constraints tc
              join information_schema.key_column_usage kcu
                   on kcu.constraint_name = tc.constraint_name
              join information_schema.constraint_column_usage ccu
                   on ccu.constraint_name = tc.constraint_name
             where tc.constraint_type='FOREIGN KEY'
               and ccu.table_name='companies' and ccu.column_name='id'
               and tc.table_schema='public'
             order by 1,2""")
    ]
    report["company_foreign_keys"] = [f"{t}.{c}" for t, c in fks]

    existing = await conn.fetch("select id, name, deleted_at from companies")
    report["existing"] = {
        "total": len(existing),
        "active_before": sum(1 for r in existing if r["deleted_at"] is None),
    }

    # Group the database's companies by normalized name. The oldest active row wins
    # so the choice is deterministic and stable across runs.
    groups: Dict[str, List[Any]] = defaultdict(list)
    for row in existing:
        if row["name"]:
            groups[norm_company(row["name"])].append(row)

    merges: List[Dict[str, Any]] = []
    keep_ids: Dict[str, Any] = {}
    for key, rows in groups.items():
        rows_sorted = sorted(rows, key=lambda r: (r["deleted_at"] is not None, str(r["id"])))
        winner = rows_sorted[0]
        keep_ids[key] = winner["id"]
        for loser in rows_sorted[1:]:
            merges.append({"key": key, "winner": str(winner["id"]), "loser": str(loser["id"]),
                           "name": loser["name"]})

    to_insert = [v for k, v in canonical.items() if k not in keep_ids]
    to_archive = [
        r["id"] for r in existing
        if r["deleted_at"] is None
        and r["name"]
        and norm_company(r["name"]) not in canonical
        and r["id"] in keep_ids.values()
    ]

    report["plan"] = {
        "duplicate_groups": sum(1 for rows in groups.values() if len(rows) > 1),
        "companies_to_merge_away": len(merges),
        "companies_to_insert": len(to_insert),
        "companies_to_archive": len(to_archive),
    }
    report["projected_active_after"] = len(canonical)

    if execute:
        tx = conn.transaction()
        await tx.start()
        try:
            now = datetime.now(timezone.utc)
            moved = defaultdict(int)
            for m in merges:
                for tbl, col in fks:
                    res = await conn.execute(
                        f'update public."{tbl}" set "{col}"=$1 where "{col}"=$2',
                        m["winner"], m["loser"],
                    )
                    n = int(res.split()[-1])
                    if n:
                        moved[f"{tbl}.{col}"] += n
                await conn.execute(
                    """update companies set deleted_at = coalesce(deleted_at, $2), updated_at = $2
                        where id = $1""",
                    m["loser"], now,
                )
            report["references_reassigned"] = dict(moved)

            for comp in to_insert:
                await conn.execute(
                    """insert into companies (id, name, status, created_at, updated_at)
                       values (gen_random_uuid(), $1, 'ACTIVE', $2, $2)""",
                    comp["name"], now,
                )
            if to_archive:
                await conn.execute(
                    """update companies set deleted_at = $2, updated_at = $2
                        where id = any($1::uuid[]) and deleted_at is null""",
                    to_archive, now,
                )
            # Re-activate anything the worksheet lists that was previously archived.
            await conn.execute(
                """update companies set deleted_at = null, updated_at = $1
                    where deleted_at is not null and id = any($2::uuid[])""",
                now, [keep_ids[k] for k in canonical if k in keep_ids],
            )
            await tx.commit()
        except Exception:
            await tx.rollback()
            await conn.close()
            raise

    report["actual_active_after"] = await conn.fetchval(
        "select count(*) from companies where deleted_at is null"
    )
    report["duplicate_active_names"] = await conn.fetchval(
        """select count(*) from (select lower(trim(name)) n from companies
            where deleted_at is null group by 1 having count(*)>1) x"""
    )
    report["orphaned_contacts"] = await conn.fetchval(
        """select count(*) from contacts c left join companies co on co.id = c.company_id
            where c.company_id is not null and co.id is null"""
    )
    await conn.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile companies against the worksheet.")
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

    rep = asyncio.run(run(args.dsn, wb, args.execute))
    w, p = rep["worksheet"], rep["plan"]
    print(f"{'EXECUTED' if rep['executed'] else 'DRY RUN (nothing written)'}   "
          f"db={rep['database']}  {rep['host']}")
    print(f"\nworksheet source rows     : {w['source_rows']}")
    print(f"  invalid                 : {w['invalid_rows']}")
    print(f"  distinct companies      : {w['distinct_companies']}")
    print(f"  name collisions         : {w['name_collisions']}")
    print(f"\ndatabase companies        : {rep['existing']['total']} "
          f"({rep['existing']['active_before']} active before)")
    print(f"  duplicate groups        : {p['duplicate_groups']}")
    print(f"  merge away              : {p['companies_to_merge_away']}")
    print(f"  insert                  : {p['companies_to_insert']}")
    print(f"  archive (not in sheet)  : {p['companies_to_archive']}")
    print(f"  company foreign keys    : {len(rep['company_foreign_keys'])}")
    if rep.get("references_reassigned"):
        for k, v in rep["references_reassigned"].items():
            print(f"      {k}: {v}")
    print(f"\nprojected active after    : {rep['projected_active_after']}")
    print(f"actual active now         : {rep['actual_active_after']}")
    print(f"duplicate active names    : {rep['duplicate_active_names']}")
    print(f"orphaned contacts         : {rep['orphaned_contacts']} (must be 0)")

    if args.out:
        Path(args.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nreport written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
