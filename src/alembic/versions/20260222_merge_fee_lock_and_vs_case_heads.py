"""Merge fee lock and gate visitor case-fix heads

Revision ID: 20260222_merge_fee_vs_case
Revises: 20260222_fee_lock_fields, 20260222_vs_case_fix
Create Date: 2026-02-22 12:40:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260222_merge_fee_vs_case"
down_revision = ("20260222_fee_lock_fields", "20260222_vs_case_fix")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge migration: no schema changes.
    pass


def downgrade() -> None:
    # Merge migration: no schema changes to revert.
    pass
