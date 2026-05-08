"""add person_type_id to visitors

Revision ID: 33e42a9c93e3
Revises: 38de87d701fd
Create Date: 2026-05-08 07:16:48.966114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33e42a9c93e3'
down_revision: Union[str, Sequence[str], None] = '38de87d701fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    # Check if person_type_id already exists
    result = bind.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name = 'visitors' AND column_name = 'person_type_id'"))
    if not result.fetchone():
        op.add_column('visitors', sa.Column('person_type_id', sa.UUID(), nullable=True))
        op.create_foreign_key('visitors_person_type_id_fkey', 'visitors', 'person_types', ['person_type_id'], ['id'], ondelete='SET NULL')
        op.create_index(op.f('ix_visitors_person_type_id'), 'visitors', ['person_type_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('visitors_person_type_id_fkey', 'visitors', type_='foreignkey')
    op.drop_index(op.f('ix_visitors_person_type_id'), table_name='visitors')
    op.drop_column('visitors', 'person_type_id')
