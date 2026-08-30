"""
Copy every table from the local SQLite database into PostgreSQL (one-time, before the
first Vercel deploy).

    cd backend
    set TARGET_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
    .venv/Scripts/python -m scripts.migrate_sqlite_to_postgres              # dry run: counts only
    .venv/Scripts/python -m scripts.migrate_sqlite_to_postgres --apply      # copy the data
    .venv/Scripts/python -m scripts.migrate_sqlite_to_postgres --apply --resume  # continue an interrupted copy
    .venv/Scripts/python -m scripts.migrate_sqlite_to_postgres --apply --reset   # drop + recreate target first

SOURCE_URL defaults to the local backend/crm.db. The target schema is created with
Base.metadata.create_all, rows are copied in foreign-key order (self-references and the
users<->teams cycle are back-filled afterwards), naive SQLite timestamps become UTC, and
alembic is stamped at head so future `alembic upgrade head` runs work.

PostgreSQL enforces foreign keys that SQLite never did, so references to rows that no
longer exist are sanitised on the way in: nullable FK columns become NULL, rows whose
non-nullable FK points nowhere are skipped (the same ON DELETE semantics the schema
declares). The local SQLite file is never modified.
"""
import argparse
import asyncio
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from sqlalchemy import DateTime, insert, select, text, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import normalize_database_url
from app.database import Base
import app.models  # noqa: F401  (register every table on Base.metadata)

SOURCE_URL = os.environ.get("SOURCE_URL", "sqlite+aiosqlite:///./crm.db")
TARGET_URL = os.environ.get("TARGET_URL", "")
CHUNK = 500


def _utc(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _deferred_columns(tables) -> Dict[str, List[str]]:
    """Columns whose FK target is inserted later (or is the same table); back-filled after the copy."""
    order = {t.name: i for i, t in enumerate(tables)}
    deferred: Dict[str, List[str]] = {}
    for t in tables:
        for fk in t.foreign_keys:
            if order[fk.column.table.name] >= order[t.name]:
                deferred.setdefault(t.name, []).append(fk.parent.name)
    return deferred


async def run(apply: bool, reset: bool, resume: bool) -> None:
    if not TARGET_URL:
        raise SystemExit("TARGET_URL is required (PostgreSQL connection string).")
    src_url, _ = normalize_database_url(SOURCE_URL)
    dst_url, pooled = normalize_database_url(TARGET_URL)
    if dst_url.startswith("sqlite"):
        raise SystemExit("TARGET_URL must be PostgreSQL.")
    connect_args = {"statement_cache_size": 0} if pooled else {}
    src = create_async_engine(src_url)
    dst = create_async_engine(dst_url, connect_args=connect_args)

    tables = list(Base.metadata.sorted_tables)
    deferred = _deferred_columns(tables)
    flags = (" + RESET" if reset else "") + (" + RESUME" if resume else "")
    print(f"source: {src_url}\ntarget: {dst_url}\nmode:   {'APPLY' if apply else 'DRY RUN'}{flags}\n")

    counts: Dict[str, int] = {}
    source_ids: Dict[str, Set[Any]] = {}
    async with src.connect() as s:
        for t in tables:
            counts[t.name] = (await s.execute(text(f'SELECT COUNT(*) FROM "{t.name}"'))).scalar_one()
            source_ids[t.name] = {r[0] for r in (await s.execute(select(t.c.id))).all()} if "id" in t.c else set()
            extra = f"   (deferred: {', '.join(deferred[t.name])})" if t.name in deferred else ""
            print(f"  {t.name:<32} {counts[t.name]:>7} rows{extra}")
    if not apply:
        print("\ndry run complete - re-run with --apply to copy.")
        await src.dispose()
        await dst.dispose()
        return

    already: Dict[str, Set[Any]] = {}
    async with dst.begin() as d:
        if reset:
            await d.run_sync(Base.metadata.drop_all)
            await d.execute(text("DROP TABLE IF EXISTS alembic_version"))
            print("target schema dropped")
        await d.run_sync(Base.metadata.create_all)
        existing = 0
        for t in tables:
            already[t.name] = {r[0] for r in (await d.execute(select(t.c.id))).all()} if "id" in t.c else set()
            existing += len(already[t.name])
        if existing and not resume:
            raise SystemExit(f"target already holds {existing} rows - refusing to copy (use --resume to continue or --reset to drop it first).")
        if existing:
            print(f"resuming: target already holds {existing} rows, existing ids will be skipped")

    inserted_ids: Dict[str, Set[Any]] = {}
    sanitized: Counter = Counter()
    backfill: List[tuple] = []

    def valid_ids(table_name: str) -> Set[Any]:
        return inserted_ids.get(table_name, source_ids[table_name])

    for t in tables:
        if not counts[t.name]:
            inserted_ids[t.name] = set(already.get(t.name, set()))
            continue
        async with src.connect() as s:
            rows = [dict(r) for r in (await s.execute(select(t))).mappings().all()]
        tz_cols = [c.name for c in t.columns if isinstance(c.type, DateTime)]
        keep: List[dict] = []
        for r in rows:
            for c in tz_cols:
                r[c] = _utc(r[c])
            skip = False
            for fk in t.foreign_keys:
                col, ref = fk.parent.name, fk.column.table.name
                val = r.get(col)
                if val is None or val in valid_ids(ref):
                    continue
                if fk.parent.nullable:
                    r[col] = None
                    sanitized[f"{t.name}.{col} -> NULL"] += 1
                else:
                    sanitized[f"{t.name} row skipped ({col} missing)"] += 1
                    skip = True
                    break
            if skip:
                continue
            for c in deferred.get(t.name, []):
                if r[c] is not None:
                    backfill.append((t, r["id"], c, r[c]))
                    r[c] = None
            keep.append(r)
        new_rows = [r for r in keep if r.get("id") not in already.get(t.name, set())]
        async with dst.begin() as d:
            for i in range(0, len(new_rows), CHUNK):
                await d.execute(insert(t), new_rows[i:i + CHUNK])
        inserted_ids[t.name] = ({r["id"] for r in keep} | already.get(t.name, set())) if "id" in t.c else set()
        note = ""
        if len(keep) != len(rows):
            note += f"  ({len(rows) - len(keep)} skipped)"
        if len(new_rows) != len(keep):
            note += f"  ({len(keep) - len(new_rows)} already present)"
        print(f"  copied {t.name:<25} {len(new_rows):>7}{note}")

    if backfill:
        applied = 0
        async with dst.begin() as d:
            for t, row_id, col, val in backfill:
                ref = next(fk.column.table.name for fk in t.foreign_keys if fk.parent.name == col)
                if val in inserted_ids.get(ref, set()):
                    await d.execute(update(t).where(t.c.id == row_id).values({col: val}))
                    applied += 1
                else:
                    sanitized[f"{t.name}.{col} -> NULL"] += 1
        print(f"  back-filled {applied} deferred foreign keys")

    if sanitized:
        print("\nsanitised dangling references (PostgreSQL enforces the FKs SQLite ignored):")
        for k, v in sorted(sanitized.items()):
            print(f"  {k:<55} {v:>5}")

    # Stamp alembic so `alembic upgrade head` is a no-op on this database
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    async with dst.begin() as d:
        await d.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        await d.execute(text("DELETE FROM alembic_version"))
        await d.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head})
    print(f"  alembic stamped at {head}")

    async with dst.connect() as d:
        mismatched = []
        for t in tables:
            got = (await d.execute(text(f'SELECT COUNT(*) FROM "{t.name}"'))).scalar_one()
            expected = len(inserted_ids.get(t.name, ()))
            if got != expected:
                mismatched.append((t.name, expected, got))
    print("\nverification:", "all table counts match" if not mismatched else f"MISMATCH {mismatched}")
    await src.dispose()
    await dst.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reset", action="store_true", help="drop and recreate the target schema before copying")
    parser.add_argument("--resume", action="store_true", help="continue into a partially filled target, skipping ids that already exist")
    args = parser.parse_args()
    asyncio.run(run(args.apply, args.reset, args.resume))
