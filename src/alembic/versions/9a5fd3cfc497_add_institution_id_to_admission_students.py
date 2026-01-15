"""add_institution_id_to_admission_students

Revision ID: 9a5fd3cfc497
Revises: 
Create Date: 2026-01-12 08:58:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a5fd3cfc497'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('admission_students', sa.Column('institution_id', sa.String(length=50), nullable=True))


def downgrade():
    op.drop_column('admission_students', 'institution_id')
