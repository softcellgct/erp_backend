"""remove_fk_constraint_from_lead_followups

Revision ID: 8b57af46c7a1
Revises: 44a1e0759a32
Create Date: 2026-02-13 09:09:57.793933

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8b57af46c7a1'
down_revision: Union[str, Sequence[str], None] = '44a1e0759a32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Remove FK constraint to allow follow-ups for both students and visitors."""
    # Drop the foreign key constraint on student_id
    op.drop_constraint('lead_followups_student_id_fkey', 'lead_followups', type_='foreignkey')


def downgrade() -> None:
    """Downgrade schema - Restore FK constraint."""
    # Restore the foreign key constraint
    op.create_foreign_key(
        'lead_followups_student_id_fkey',
        'lead_followups',
        'admission_students',
        ['student_id'],
        ['id'],
        ondelete='CASCADE'
    )
