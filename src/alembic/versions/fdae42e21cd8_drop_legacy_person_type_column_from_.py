"""drop legacy person_type column from visitors

Revision ID: fdae42e21cd8
Revises: 33e42a9c93e3
Create Date: 2026-05-08 07:42:18.844200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdae42e21cd8'
down_revision: Union[str, Sequence[str], None] = '33e42a9c93e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if column exists before dropping to avoid errors in different environments
    bind = op.get_bind()
    result = bind.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name = 'visitors' AND column_name = 'person_type'"))
    if result.fetchone():
        op.drop_column('visitors', 'person_type')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('visitors', sa.Column('person_type', sa.String(length=255), nullable=True))
