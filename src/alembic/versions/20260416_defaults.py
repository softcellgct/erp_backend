"""Add server defaults to source, is_sem1_active, is_fee_structure_locked.

Revision ID: 20260416_defaults
Revises: 20260416_add_name
Create Date: 2026-04-16 10:26:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260416_defaults'
down_revision = '20260416_add_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Server defaults are handled in model definitions
    # This migration is a placeholder for future use
    pass


def downgrade() -> None:
    # Server defaults are handled in model definitions
    # This migration is a placeholder for future use
    pass
