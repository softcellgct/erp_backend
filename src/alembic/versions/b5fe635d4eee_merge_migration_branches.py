"""merge_migration_branches

Revision ID: b5fe635d4eee
Revises: 20260416_defaults, a46bfa0772e8
Create Date: 2026-04-17 15:33:41.826393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5fe635d4eee'
down_revision: Union[str, Sequence[str], None] = ('20260416_defaults', 'a46bfa0772e8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
