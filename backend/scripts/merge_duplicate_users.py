"""
Merge duplicate user accounts into their canonical account.

Two people in this CRM exist twice, and the duplicate holds all the data:

    hasan@alphapromena.com   ->  hassan@alphapromena.com
    qusai@alphapro.com       ->  qusai@alphapromena.com

Hassan signs in as the canonical spelling, which owns almost nothing, while the
misspelled account owns his real contacts. That is why he sees no leads.

Every foreign key that references users is discovered from the live schema rather
than hardcoded, so a column added later is still moved. The whole merge runs in one
transaction: either every reference moves and the duplicate is retired, or nothing
changes.

Safe by default. Without --execute it only reports what it would do.

    python backend/scripts/merge_duplicate_users.py                 # dry run
    python backend/scripts/merge_duplicate_users.py --execute       # apply

The connection string comes from DATABASE_URL, or --dsn. Nothing is printed that
would expose it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# duplicate -> canonical
DEFAULT_PAIRS: List[Tuple[str, str]] = [
    ("hasan@alphapromena.com", "hassan@alphapromena.com"),
    ("qusai@alphapro.com", "qusai@alphapromena.com"),
]

FK_QUERY = """
select tc.table_name as tbl, kcu.column_name as col
from information_schema.table_constraints tc
join information_schema.key_column_usage kcu
     on kcu.constraint_name = tc.constraint_name
    and kcu.table_schema = tc.table_schema
join information_schema.constraint_column_usage ccu
     on ccu.constraint_name = tc.constraint_name
    and ccu.table_schema = tc.table_schema
where tc.constraint_type = 'FOREIGN KEY'
  and ccu.table_name = 'users'
  and ccu.column_name = 'id'
  and tc.table_schema = 'public'
order by 1, 2
"""


def clean_dsn(dsn: str) -> str:
    """asyncpg rejects libpq-only query parameters."""
    return re.sub(r"[?&](sslmode|channel_binding|options)=[^&]*", "", dsn.strip())


def redact(dsn: str) -> str:
    m = re.search(r"@([^/?]+)", dsn)
    return f"host={m.group(1)}" if m else "host=<unknown>"


async def merge(dsn: str, pairs: List[Tuple[str, str]], execute: bool) -> Dict[str, Any]:
    import asyncpg

    conn = await asyncpg.connect(clean_dsn(dsn), ssl="require", timeout=60)
    report: Dict[str, Any] = {
        "database": await conn.fetchval("select current_database()"),
        "host": redact(dsn),
        "executed": execute,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pairs": [],
    }

    fks = [(r["tbl"], r["col"]) for r in await conn.fetch(FK_QUERY)]
    report["user_foreign_keys"] = [f"{t}.{c}" for t, c in fks]

    tx = conn.transaction()
    await tx.start()
    try:
        for dup_email, canon_email in pairs:
            entry: Dict[str, Any] = {
                "duplicate": dup_email,
                "canonical": canon_email,
                "moves": {},
                "rows_moved": 0,
            }

            dup = await conn.fetchrow(
                "select id, is_active, deleted_at from users where lower(email)=lower($1)", dup_email
            )
            canon = await conn.fetchrow(
                "select id from users where lower(email)=lower($1) and deleted_at is null", canon_email
            )

            if dup is None:
                entry["status"] = "already merged or absent"
                report["pairs"].append(entry)
                continue
            if canon is None:
                entry["status"] = "ERROR: canonical account missing; refusing to merge"
                report["pairs"].append(entry)
                continue
            if dup["id"] == canon["id"]:
                entry["status"] = "same account; nothing to do"
                report["pairs"].append(entry)
                continue

            for tbl, col in fks:
                if execute:
                    res = await conn.execute(
                        f'update public."{tbl}" set "{col}"=$1 where "{col}"=$2',
                        canon["id"], dup["id"],
                    )
                    moved = int(res.split()[-1])
                else:
                    moved = await conn.fetchval(
                        f'select count(*) from public."{tbl}" where "{col}"=$1', dup["id"]
                    )
                if moved:
                    entry["moves"][f"{tbl}.{col}"] = moved
                    entry["rows_moved"] += moved

            if execute:
                # Retire the duplicate without destroying it. The email is prefixed so
                # the unique constraint cannot block a future canonical account, and so
                # the original address stays readable in the row.
                await conn.execute(
                    """update users
                          set is_active = false,
                              deleted_at = coalesce(deleted_at, now()),
                              email = case when email like 'merged+%' then email
                                           else 'merged+' || email end
                        where id = $1""",
                    dup["id"],
                )
                try:
                    await conn.execute(
                        """insert into audit_logs (id, action, entity_type, entity_id, actor_id, notes, created_at)
                           values (gen_random_uuid(), 'user.merged', 'user', $1, $2, $3, now())""",
                        dup["id"], canon["id"],
                        f"Merged {dup_email} into {canon_email}; {entry['rows_moved']} references reassigned",
                    )
                    entry["audit_logged"] = True
                except Exception as exc:  # audit shape varies; never fail the merge on it
                    entry["audit_logged"] = False
                    entry["audit_error"] = str(exc)[:160]

            entry["status"] = "merged" if execute else "would merge"
            report["pairs"].append(entry)

        if execute:
            await tx.commit()
        else:
            await tx.rollback()
    except Exception:
        await tx.rollback()
        await conn.close()
        raise

    report["post_state"] = [
        {"email": r["email"], "is_active": r["is_active"], "contacts": r["n"]}
        for r in await conn.fetch(
            """select u.email, u.is_active,
                      (select count(*) from contacts x
                        where x.owner_id = u.id and x.deleted_at is null) n
                 from users u where u.deleted_at is null order by u.email"""
        )
    ]
    await conn.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge duplicate user accounts.")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    ap.add_argument("--execute", action="store_true", help="apply changes (default is a dry run)")
    ap.add_argument("-o", "--out", default="")
    args = ap.parse_args()

    if not args.dsn:
        print("ERROR: no connection string. Pass --dsn or set DATABASE_URL.", file=sys.stderr)
        return 2

    report = asyncio.run(merge(args.dsn, DEFAULT_PAIRS, args.execute))

    mode = "EXECUTED" if report["executed"] else "DRY RUN (no changes written)"
    print(f"{mode}  database={report['database']}  {report['host']}")
    print(f"user foreign keys discovered: {len(report['user_foreign_keys'])}")
    for p in report["pairs"]:
        print(f"\n  {p['duplicate']} -> {p['canonical']}: {p['status']}")
        for ref, n in p["moves"].items():
            print(f"      {ref}: {n}")
        if p["moves"]:
            print(f"      total references: {p['rows_moved']}")
    print("\nactive users after this operation:")
    for u in report["post_state"]:
        print(f"   {u['email']:<34} active={u['is_active']}  contacts={u['contacts']}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"\nreport written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
