"""crm operational workflows: task archive, follow-up flex, demo conversion, opportunity fields

Revision ID: a9f3e2d1c4b7
Revises: c7e91f4a2b38
Create Date: 2026-09-15 09:58:00.000000+00:00

Adds exactly the missing columns based on DB introspection:
  tasks         — add archived_at, archived_by (req 12)
  follow_ups    — make contact_id nullable; add company_name_snapshot,
                  meeting_with, demo_id  (next_step already exists)
  demos         — add company_name_snapshot, meeting_with,
                  converted_to_follow_up_at, converted_to_follow_up_id
  opportunities — add company_name_snapshot, contact_person, notes, next_step
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9f3e2d1c4b7'
down_revision: Union[str, None] = 'c7e91f4a2b38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. tasks: archive columns ─────────────────────────────────────────
    op.add_column('tasks', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tasks', sa.Column('archived_by', sa.Uuid(), nullable=True))
    op.create_index('idx_tasks_archived_at', 'tasks', ['archived_at'])

    # ── 2. follow_ups: new columns + make contact_id nullable ─────────────
    # Add the new columns first (no batch needed for simple adds in SQLite)
    op.add_column('follow_ups', sa.Column('company_name_snapshot', sa.String(500), nullable=True))
    op.add_column('follow_ups', sa.Column('meeting_with', sa.String(255), nullable=True))
    op.add_column('follow_ups', sa.Column('demo_id', sa.Uuid(), nullable=True))
    op.create_index('idx_follow_ups_demo_id', 'follow_ups', ['demo_id'])

    # Make contact_id and due_at nullable — requires batch_alter in SQLite
    with op.batch_alter_table('follow_ups', schema=None) as batch_op:
        batch_op.alter_column(
            'contact_id',
            existing_type=sa.Uuid(),
            nullable=True,
        )
        batch_op.alter_column(
            'due_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )

    # ── 3. demos: company snapshot, meeting_with, follow-up conversion ────
    op.add_column('demos', sa.Column('company_name_snapshot', sa.String(500), nullable=True))
    op.add_column('demos', sa.Column('meeting_with', sa.String(255), nullable=True))
    op.add_column('demos', sa.Column('converted_to_follow_up_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('demos', sa.Column('converted_to_follow_up_id', sa.Uuid(), nullable=True))

    # ── 4. opportunities: snapshot & enrichment columns ───────────────────
    op.add_column('opportunities', sa.Column('company_name_snapshot', sa.String(500), nullable=True))
    op.add_column('opportunities', sa.Column('contact_person', sa.String(255), nullable=True))
    op.add_column('opportunities', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('opportunities', sa.Column('next_step', sa.Text(), nullable=True))


def downgrade() -> None:
    # ── 4. opportunities ──────────────────────────────────────────────────
    op.drop_column('opportunities', 'next_step')
    op.drop_column('opportunities', 'notes')
    op.drop_column('opportunities', 'contact_person')
    op.drop_column('opportunities', 'company_name_snapshot')

    # ── 3. demos ──────────────────────────────────────────────────────────
    op.drop_column('demos', 'converted_to_follow_up_id')
    op.drop_column('demos', 'converted_to_follow_up_at')
    op.drop_column('demos', 'meeting_with')
    op.drop_column('demos', 'company_name_snapshot')

    # ── 2. follow_ups ─────────────────────────────────────────────────────
    op.drop_index('idx_follow_ups_demo_id', table_name='follow_ups')
    op.drop_column('follow_ups', 'demo_id')
    op.drop_column('follow_ups', 'meeting_with')
    op.drop_column('follow_ups', 'company_name_snapshot')
    # Restore contact_id NOT NULL (rows with null values are historical imports)
    with op.batch_alter_table('follow_ups', schema=None) as batch_op:
        batch_op.alter_column(
            'contact_id',
            existing_type=sa.Uuid(),
            nullable=False,
        )
        batch_op.alter_column(
            'due_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )

    # ── 1. tasks ──────────────────────────────────────────────────────────
    op.drop_index('idx_tasks_archived_at', table_name='tasks')
    op.drop_column('tasks', 'archived_by')
    op.drop_column('tasks', 'archived_at')
