"""Update school_master table with address and pincode fields

Revision ID: 20260227_update_school_master
Revises: admission_redesign_001
Create Date: 2026-02-27 14:00:00.000000

Changes:
1. Add school_address column to school_master
2. Add pincode column to school_master
3. Rename name column context to match PDF structure (school_name)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260227_update_school_master'
down_revision = 'admission_redesign_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add school_address column if it doesn't exist
    with op.batch_alter_table('school_master', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('school_address', sa.String(500), nullable=True)
        )
        batch_op.add_column(
            sa.Column('pincode', sa.String(6), nullable=True)
        )
        # Add index on district for filtering
        batch_op.create_index('ix_school_master_district', ['district'], if_not_exists=True)
        # Add index on pincode for searching
        batch_op.create_index('ix_school_master_pincode', ['pincode'], if_not_exists=True)


def downgrade() -> None:
    with op.batch_alter_table('school_master', schema=None) as batch_op:
        batch_op.drop_index('ix_school_master_pincode', if_exists=True)
        batch_op.drop_index('ix_school_master_district', if_exists=True)
        batch_op.drop_column('pincode')
        batch_op.drop_column('school_address')
