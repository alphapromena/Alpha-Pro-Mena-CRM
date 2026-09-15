"""leads_archive provenance and duplicate protection

The archive could not answer two questions it needs to answer: which file a row
came from, and what the source columns were called. It also had nothing stopping
the same workbook being archived twice.

Adds:
  source_file_checksum  sha256 of the workbook the row came from
  header_json           the worksheet's real header, so raw_data stays readable
                        without guessing at column order
  source_row_sha        sha256 of the row's own cells

and a unique index on (source_file_checksum, sheet_name, row_number), which is
what makes re-uploading the same workbook a no-op instead of a second copy.

Reversible: downgrade drops exactly what upgrade added.

Revision ID: a4d2c8b19e77
Revises: c5a1f8e23901
Create Date: 2026-09-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4d2c8b19e77"
down_revision: Union[str, None] = "c5a1f8e23901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "leads_archive"
UNIQUE_INDEX = "uq_leads_archive_file_sheet_row"


def upgrade() -> None:
    # Nullable on the way in: existing rows predate these columns and there is no
    # honest value to backfill them with.
    op.add_column(TABLE, sa.Column("source_file_checksum", sa.String(64), nullable=True))
    op.add_column(TABLE, sa.Column("header_json", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("source_row_sha", sa.String(64), nullable=True))

    op.create_index(
        "idx_leads_archive_file_checksum", TABLE, ["source_file_checksum"], unique=False
    )
    op.create_index("idx_leads_archive_row_number", TABLE, ["row_number"], unique=False)

    # The duplicate guard. Partial, because rows archived before this migration have
    # no checksum and must not all collide on NULL.
    op.create_index(
        UNIQUE_INDEX,
        TABLE,
        ["source_file_checksum", "sheet_name", "row_number"],
        unique=True,
        postgresql_where=sa.text("source_file_checksum IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(UNIQUE_INDEX, table_name=TABLE)
    op.drop_index("idx_leads_archive_row_number", table_name=TABLE)
    op.drop_index("idx_leads_archive_file_checksum", table_name=TABLE)
    op.drop_column(TABLE, "source_row_sha")
    op.drop_column(TABLE, "header_json")
    op.drop_column(TABLE, "source_file_checksum")
