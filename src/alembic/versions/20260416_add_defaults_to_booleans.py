"""Add server defaults to source, is_sem1_active, and is_fee_structure_locked columns.

Revision ID: 20260416_add_defaults_to_booleans
Revises: 20260416_fix_lateral_entry
Create Date: 2026-04-16 10:26:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260416_add_defaults_to_booleans'
down_revision = '20260416_fix_lateral_entry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add GATE_ENQUIRY default to source column
    try:
        op.alter_column('admission_students', 'source',
                       existing_type=sa.Enum('GATE_ENQUIRY', 'DIRECT_ENTRY', 'COUNSELING', name='sourceenum'),
                       server_default='GATE_ENQUIRY',
                       existing_nullable=False)
    except Exception as e:
        print(f"source column: {e}")

    # Add false default to is_sem1_active column
    try:
        op.alter_column('admission_students', 'is_sem1_active',
                       existing_type=sa.Boolean(),
                       server_default=sa.literal(False),
                       existing_nullable=False)
    except Exception as e:
        print(f"is_sem1_active column: {e}")

    # Add false default to is_fee_structure_locked column
    try:
        op.alter_column('admission_students', 'is_fee_structure_locked',
                       existing_type=sa.Boolean(),
                       server_default=sa.literal(False),
                       existing_nullable=False)
    except Exception as e:
        print(f"is_fee_structure_locked column: {e}")


def downgrade() -> None:
    # Remove server defaults
    try:
        op.alter_column('admission_students', 'source',
                       existing_type=sa.Enum('GATE_ENQUIRY', 'DIRECT_ENTRY', 'COUNSELING', name='sourceenum'),
                       server_default=None,
                       existing_nullable=False)
    except Exception as e:
        print(f"source column: {e}")

    try:
        op.alter_column('admission_students', 'is_sem1_active',
                       existing_type=sa.Boolean(),
                       server_default=None,
                       existing_nullable=False)
    except Exception as e:
        print(f"is_sem1_active column: {e}")

    try:
        op.alter_column('admission_students', 'is_fee_structure_locked',
                       existing_type=sa.Boolean(),
                       server_default=None,
                       existing_nullable=False)
    except Exception as e:
        print(f"is_fee_structure_locked column: {e}")
