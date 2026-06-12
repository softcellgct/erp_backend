"""create sis_roll_number_templates table

Revision ID: pe20260530c
Revises: pe20260530b
Create Date: 2026-05-30 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'pe20260530c'
down_revision: Union[str, Sequence[str], None] = 'pe20260530b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sis_roll_number_templates',
        sa.Column('institution_id', sa.UUID(), nullable=True),
        sa.Column('department_id', sa.UUID(), nullable=True),
        sa.Column('course_id', sa.UUID(), nullable=True),
        sa.Column('academic_year_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=150), nullable=True),
        sa.Column('tokens', sa.JSON(), nullable=False),
        sa.Column('separator', sa.String(length=5), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_roll_template_created_by_users', initially='DEFERRED', deferrable=True, use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_roll_template_updated_by_users', initially='DEFERRED', deferrable=True, use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_roll_template_deleted_by_users', initially='DEFERRED', deferrable=True, use_alter=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('department_id', 'academic_year_id', name='uq_roll_template_dept_year'),
    )
    op.create_index(op.f('ix_sis_roll_number_templates_deleted_at'), 'sis_roll_number_templates', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_sis_roll_number_templates_institution_id'), 'sis_roll_number_templates', ['institution_id'], unique=False)
    op.create_index(op.f('ix_sis_roll_number_templates_department_id'), 'sis_roll_number_templates', ['department_id'], unique=False)
    op.create_index(op.f('ix_sis_roll_number_templates_course_id'), 'sis_roll_number_templates', ['course_id'], unique=False)
    op.create_index(op.f('ix_sis_roll_number_templates_academic_year_id'), 'sis_roll_number_templates', ['academic_year_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sis_roll_number_templates_academic_year_id'), table_name='sis_roll_number_templates')
    op.drop_index(op.f('ix_sis_roll_number_templates_course_id'), table_name='sis_roll_number_templates')
    op.drop_index(op.f('ix_sis_roll_number_templates_department_id'), table_name='sis_roll_number_templates')
    op.drop_index(op.f('ix_sis_roll_number_templates_institution_id'), table_name='sis_roll_number_templates')
    op.drop_index(op.f('ix_sis_roll_number_templates_deleted_at'), table_name='sis_roll_number_templates')
    op.drop_table('sis_roll_number_templates')
