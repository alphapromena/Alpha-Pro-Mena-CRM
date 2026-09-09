"""crm security, demo reporting, and historical demo tracking

Revision ID: c5a1f8e23901
Revises: b6d7df55ae73
Create Date: 2026-09-09 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5a1f8e23901'
down_revision: Union[str, None] = 'b6d7df55ae73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Users table security & verification additions ───────────────
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('verification_token_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('verification_token_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('verification_sent_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('password_reset_token_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('password_reset_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('password_reset_sent_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_users_verification_token_hash', ['verification_token_hash'], unique=False)
        batch_op.create_index('ix_users_password_reset_token_hash', ['password_reset_token_hash'], unique=False)

    # ── 2. Demos table reporting & history additions ───────────────────
    with op.batch_alter_table('demos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=50), server_default=sa.text("'PENDING'"), nullable=False))
        batch_op.add_column(sa.Column('presenter', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('attendees', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('topics_covered', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('next_step', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('next_step_due_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('report_status', sa.String(length=30), server_default=sa.text("'NEEDS_REPORT'"), nullable=False))
        batch_op.add_column(sa.Column('is_historical', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('historical_source', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('historical_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('created_by_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('updated_by_id', sa.Uuid(), nullable=True))

        batch_op.create_foreign_key('fk_demos_created_by_id_users', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_demos_updated_by_id_users', 'users', ['updated_by_id'], ['id'], ondelete='SET NULL')

        batch_op.create_index('ix_demos_status', ['status'], unique=False)
        batch_op.create_index('ix_demos_next_step_due_date', ['next_step_due_date'], unique=False)
        batch_op.create_index('ix_demos_report_status', ['report_status'], unique=False)
        batch_op.create_index('ix_demos_is_historical', ['is_historical'], unique=False)
        batch_op.create_index('ix_demos_historical_date', ['historical_date'], unique=False)
        batch_op.create_index('ix_demos_created_by_id', ['created_by_id'], unique=False)
        batch_op.create_index('idx_demos_owner_status', ['owner_id', 'status'], unique=False)

    # ── 3. Backfill report_status for existing demos ───────────────────
    op.execute(
        sa.text(
            "UPDATE demos SET report_status = 'REPORT_COMPLETE' "
            "WHERE summary IS NOT NULL AND TRIM(summary) != ''"
        )
    )
    op.execute(
        sa.text(
            "UPDATE demos SET report_status = 'NEEDS_REPORT' "
            "WHERE summary IS NULL OR TRIM(summary) = ''"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table('demos', schema=None) as batch_op:
        batch_op.drop_index('idx_demos_owner_status')
        batch_op.drop_index('ix_demos_created_by_id')
        batch_op.drop_index('ix_demos_historical_date')
        batch_op.drop_index('ix_demos_is_historical')
        batch_op.drop_index('ix_demos_report_status')
        batch_op.drop_index('ix_demos_next_step_due_date')
        batch_op.drop_index('ix_demos_status')
        batch_op.drop_constraint('fk_demos_updated_by_id_users', type_='foreignkey')
        batch_op.drop_constraint('fk_demos_created_by_id_users', type_='foreignkey')
        batch_op.drop_column('updated_by_id')
        batch_op.drop_column('created_by_id')
        batch_op.drop_column('historical_date')
        batch_op.drop_column('historical_source')
        batch_op.drop_column('is_historical')
        batch_op.drop_column('report_status')
        batch_op.drop_column('next_step_due_date')
        batch_op.drop_column('next_step')
        batch_op.drop_column('reason')
        batch_op.drop_column('summary')
        batch_op.drop_column('topics_covered')
        batch_op.drop_column('attendees')
        batch_op.drop_column('presenter')
        batch_op.drop_column('status')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_password_reset_token_hash')
        batch_op.drop_index('ix_users_verification_token_hash')
        batch_op.drop_column('password_reset_sent_at')
        batch_op.drop_column('password_reset_expires_at')
        batch_op.drop_column('password_reset_token_hash')
        batch_op.drop_column('verification_sent_at')
        batch_op.drop_column('verification_token_expires_at')
        batch_op.drop_column('verification_token_hash')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('must_change_password')
