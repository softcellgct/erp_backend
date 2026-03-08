"""merge_school_and_staff_migrations

Revision ID: 8d5468ceb984
Revises: 20260227_update_school_master, student_ref_roll_number_001
Create Date: 2026-03-08 16:12:34.144140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d5468ceb984'
down_revision: Union[str, Sequence[str], None] = ('20260227_update_school_master', 'student_ref_roll_number_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
