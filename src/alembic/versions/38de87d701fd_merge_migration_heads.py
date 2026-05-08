"""merge migration heads

Revision ID: 38de87d701fd
Revises: 4ac8ad16ca1a, 20260417_drop_legacy_student_program
Create Date: 2026-05-08 07:16:37.729855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38de87d701fd'
down_revision: Union[str, Sequence[str], None] = ('4ac8ad16ca1a', '20260417_drop_legacy')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
