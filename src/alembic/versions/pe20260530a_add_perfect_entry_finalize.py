"""add perfect entry finalize columns to admission_students

Revision ID: pe20260530a
Revises: pe20260520
Create Date: 2026-05-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'pe20260530a'
down_revision: Union[str, Sequence[str], None] = 'pe20260520'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'admission_students',
        sa.Column('perfect_entry_finalized', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'admission_students',
        sa.Column('perfect_entry_finalized_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'admission_students',
        sa.Column('perfect_entry_finalized_by', sa.UUID(), nullable=True),
    )
    op.create_index(
        op.f('ix_admission_students_perfect_entry_finalized_by'),
        'admission_students',
        ['perfect_entry_finalized_by'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_admission_students_pe_finalized_by_users',
        'admission_students',
        'users',
        ['perfect_entry_finalized_by'],
        ['id'],
        initially='DEFERRED',
        deferrable=True,
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint('fk_admission_students_pe_finalized_by_users', 'admission_students', type_='foreignkey')
    op.drop_index(op.f('ix_admission_students_perfect_entry_finalized_by'), table_name='admission_students')
    op.drop_column('admission_students', 'perfect_entry_finalized_by')
    op.drop_column('admission_students', 'perfect_entry_finalized_at')
    op.drop_column('admission_students', 'perfect_entry_finalized')
