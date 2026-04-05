"""Add AcademicYearDepartment model for fees

Revision ID: 4a5576c257cc
Revises: 0c7084aeb2a0
Create Date: 2026-01-15 09:49:41.815849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4a5576c257cc'
down_revision: Union[str, Sequence[str], None] = '0c7084aeb2a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('academic_year_departments',
    sa.Column('academic_year_id', sa.UUID(), nullable=False),
    sa.Column('department_id', sa.UUID(), nullable=False),
    sa.Column('application_fee', sa.Float(), nullable=False, server_default='0.0'),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('updated_by', sa.UUID(), nullable=True),
    sa.Column('deleted_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], use_alter=True),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], use_alter=True),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], use_alter=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_academic_year_departments_academic_year_id'), 'academic_year_departments', ['academic_year_id'], unique=False)
    op.create_index(op.f('ix_academic_year_departments_department_id'), 'academic_year_departments', ['department_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_academic_year_departments_department_id'), table_name='academic_year_departments')
    op.drop_index(op.f('ix_academic_year_departments_academic_year_id'), table_name='academic_year_departments')
    op.drop_table('academic_year_departments')
