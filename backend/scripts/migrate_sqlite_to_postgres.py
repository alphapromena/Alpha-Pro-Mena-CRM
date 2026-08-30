"""
Copy every table from the local SQLite database into PostgreSQL (one-time, before the
first Vercel deploy).

    cd backend
    set TARGET_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
    .venv/Scripts/python -m scripts.migrate_sqlite_to_postgres              # dry run: counts only
    .venv/Scripts/python -m scripts.migrate_sqlite_to_postgres --apply      # copy the data

SOURCE_URL defaults to the local backend/crm.db. The target schema is created with
Base.metadata.create_all, rows are copied in foreign-key order (self-references and the
users<->teams cycle are back-filled afterwards), naive SQLite timestamps become UTC, and
alembic is stamped at head so future `alembic upgrade head` runs work.
"""
import argparse
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

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


async def run(apply: bool) -> None:
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
    print(f"source: {src_url}\ntarget: {dst_url}\nmode:   {'APPLY' if apply else 'DRY RUN'}\n")

    counts: Dict[str, int] = {}
    async with src.connect() as s:
        for t in tables:
            counts[t.name] = (await s.execute(text(f'SELECT COUNT(*) FROM "{t.name}"'))).scalar_one()
            extra = f"   (deferred: {', '.join(deferred[t.name])})" if t.name in deferred else ""
            print(f"  {t.name:<32} {counts[t.name]:>7} rows{extra}")
    if not apply:
        print("\ndry run complete - re-run with --apply to copy.")
        await src.dispose()
        await dst.dispose()
        return

    async with dst.begin() as d:
        await d.run_sync(Base.metadata.create_all)
        existing = 0
        for t in tables:
            existing += (await d.execute(text(f'SELECT COUNT(*) FROM "{t.name}"'))).scalar_one()
        if existing:
            raise SystemExit(f"target already holds {existing} rows - refusing to copy into a non-empty database.")

    backfill: List[tuple] = []
    for t in tables:
        if not counts[t.name]:
            continue
        async with src.connect() as s:
            rows = [dict(r) for r in (await s.execute(select(t))).mappings().all()]
        tz_cols = [c.name for c in t.columns if isinstance(c.type, DateTime)]
        for r in rows:
            for c in tz_cols:
                r[c] = _utc(r[c])
            for c in deferred.get(t.name, []):
                if r[c] is not None:
                    backfill.append((t, r["id"], c, r[c]))
                    r[c] = None
        async with dst.begin() as d:
            for i in range(0, len(rows), CHUNK):
                await d.execute(insert(t), rows[i:i + CHUNK])
        print(f"  copied {t.name:<25} {len(rows):>7}")

    if backfill:
        async with dst.begin() as d:
            for t, row_id, col, val in backfill:
                await d.execute(update(t).where(t.c.id == row_id).values({col: val}))
        print(f"  back-filled {len(backfill)} deferred foreign keys")

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
            if got != counts[t.name]:
                mismatched.append((t.name, counts[t.name], got))
    print("\nverification:", "all table counts match" if not mismatched else f"MISMATCH {mismatched}")
    await src.dispose()
    await dst.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
