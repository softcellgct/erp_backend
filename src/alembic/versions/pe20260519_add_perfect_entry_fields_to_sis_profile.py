"""add perfect entry fields to sis_student_profiles

Revision ID: pe20260519
Revises: fdae42e21cd8
Create Date: 2026-05-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'pe20260519'
down_revision: Union[str, Sequence[str], None] = 'fdae42e21cd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sis_student_profiles', sa.Column('bank_name', sa.String(200), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('bank_account_number', sa.String(50), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('bank_ifsc_code', sa.String(20), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('bank_branch_name', sa.String(200), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('bank_account_holder_name', sa.String(200), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('tc_number', sa.String(50), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('tc_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('tc_from_school', sa.String(200), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('tc_issued_by', sa.String(200), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('emergency_contact_name', sa.String(200), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('emergency_contact_relation', sa.String(100), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('emergency_contact_mobile', sa.String(15), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('counselling_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('counselling_number', sa.String(50), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('allotment_order_number', sa.String(50), nullable=True))
    op.add_column('sis_student_profiles', sa.Column('counselling_type', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('sis_student_profiles', 'counselling_type')
    op.drop_column('sis_student_profiles', 'allotment_order_number')
    op.drop_column('sis_student_profiles', 'counselling_number')
    op.drop_column('sis_student_profiles', 'counselling_date')
    op.drop_column('sis_student_profiles', 'emergency_contact_mobile')
    op.drop_column('sis_student_profiles', 'emergency_contact_relation')
    op.drop_column('sis_student_profiles', 'emergency_contact_name')
    op.drop_column('sis_student_profiles', 'tc_issued_by')
    op.drop_column('sis_student_profiles', 'tc_from_school')
    op.drop_column('sis_student_profiles', 'tc_date')
    op.drop_column('sis_student_profiles', 'tc_number')
    op.drop_column('sis_student_profiles', 'bank_account_holder_name')
    op.drop_column('sis_student_profiles', 'bank_branch_name')
    op.drop_column('sis_student_profiles', 'bank_ifsc_code')
    op.drop_column('sis_student_profiles', 'bank_account_number')
    op.drop_column('sis_student_profiles', 'bank_name')
