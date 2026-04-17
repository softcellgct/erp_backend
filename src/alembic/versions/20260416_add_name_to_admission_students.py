"""Add name column back to admission_students

Revision ID: 20260416_add_name
Revises: scholarship_config_001
Create Date: 2026-04-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260416_add_name'
down_revision: Union[str, Sequence[str], None] = 'scholarship_config_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add name column to admission_students."""
    # Add the name column with a default value
    op.add_column('admission_students', sa.Column('name', sa.String(length=200), nullable=False, server_default='Unknown'))
    op.create_index(op.f('ix_admission_students_name'), 'admission_students', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema - drop name column from admission_students."""
    op.drop_index(op.f('ix_admission_students_name'), table_name='admission_students')
    op.drop_column('admission_students', 'name')
