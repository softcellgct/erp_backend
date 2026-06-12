"""add govt, address, and contact fields to sis_student_profiles

Revision ID: pe20260520
Revises: pe20260519
Create Date: 2026-05-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'pe20260520'
down_revision: Union[str, Sequence[str], None] = 'pe20260519'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Government / institutional IDs
    op.add_column('sis_student_profiles', sa.Column('emis_number', sa.String(50), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('umis_number', sa.String(50), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('abc_id', sa.String(50), nullable=True))

    # Quota / social status
    op.add_column('sis_student_profiles', sa.Column('minority_status', sa.String(100), nullable=True))

    # Contact extras
    op.add_column('sis_student_profiles', sa.Column('alternate_mobile', sa.String(15), nullable=True))

    # Extended communication address
    op.add_column('sis_student_profiles', sa.Column('comm_address_line2', sa.String(500), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('comm_country', sa.String(100), nullable=True, server_default='India'))

    # Structured permanent address
    op.add_column('sis_student_profiles', sa.Column('perm_address_line1', sa.String(500), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('perm_address_line2', sa.String(500), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('perm_area_street', sa.String(500), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('perm_city', sa.String(100), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('perm_district', sa.String(100), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('perm_state', sa.String(100), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('perm_country', sa.String(100), nullable=True, server_default='India'))
    op.add_column('sis_student_profiles', sa.Column('perm_pincode', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('sis_student_profiles', 'perm_pincode')
    op.drop_column('sis_student_profiles', 'perm_country')
    op.drop_column('sis_student_profiles', 'perm_state')
    op.drop_column('sis_student_profiles', 'perm_district')
    op.drop_column('sis_student_profiles', 'perm_city')
    op.drop_column('sis_student_profiles', 'perm_area_street')
    op.drop_column('sis_student_profiles', 'perm_address_line2')
    op.drop_column('sis_student_profiles', 'perm_address_line1')
    op.drop_column('sis_student_profiles', 'comm_country')
    op.drop_column('sis_student_profiles', 'comm_address_line2')
    op.drop_column('sis_student_profiles', 'alternate_mobile')
    op.drop_column('sis_student_profiles', 'minority_status')
    op.drop_column('sis_student_profiles', 'abc_id')
    op.drop_column('sis_student_profiles', 'umis_number')
    op.drop_column('sis_student_profiles', 'emis_number')
