"""historical activity import keys, and undated follow-ups

Importing historical demos and follow-ups needs two things the schema does not
yet allow.

First, an idempotency key. Without one, re-uploading the same workbook inserts
the activities a second time. import_key holds a hash of
(file checksum, worksheet, source row, activity type, row checksum) and is
uniquely indexed, so the guard lives in the database rather than in whichever
script happens to run.

Second, follow_ups.due_at is NOT NULL, but most historical follow-ups have no
date at all: the source cell says "No Answer" or "Asked for email". The only
honest options are to refuse those rows or to let the column be null, and
refusing would discard 189 of 253 real activities. Inventing a date is not an
option, because a row nobody touched would look like it happened today.

Reversible, with one caveat noted in downgrade.

Revision ID: c7e91f4a2b38
Revises: a4d2c8b19e77
Create Date: 2026-09-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7e91f4a2b38"
down_revision: Union[str, None] = "a4d2c8b19e77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("demos", "follow_ups"):
        op.add_column(table, sa.Column("import_key", sa.String(64), nullable=True))
        # Partial, so the many rows created by hand through the UI, which have no
        # import key, do not all collide on NULL.
        op.create_index(
            f"uq_{table}_import_key",
            table,
            ["import_key"],
            unique=True,
            postgresql_where=sa.text("import_key IS NOT NULL"),
        )
        op.add_column(table, sa.Column("source_file_checksum", sa.String(64), nullable=True))
        op.create_index(f"idx_{table}_source_file", table, ["source_file_checksum"])

    # A historical follow-up genuinely has no due date.
    op.alter_column("follow_ups", "due_at", existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade() -> None:
    # Rows with a null due_at cannot exist under the old constraint. They are
    # historical imports, so they are removed rather than given an invented date.
    op.execute("DELETE FROM follow_ups WHERE due_at IS NULL")
    op.alter_column("follow_ups", "due_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    for table in ("demos", "follow_ups"):
        op.drop_index(f"idx_{table}_source_file", table_name=table)
        op.drop_column(table, "source_file_checksum")
        op.drop_index(f"uq_{table}_import_key", table_name=table)
        op.drop_column(table, "import_key")
