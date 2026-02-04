"""add_admission_type_to_admission_students

Revision ID: 4e0ce516d9c1
Revises: 011d614e2802
Create Date: 2026-01-31 06:58:09.608693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e0ce516d9c1'
down_revision: Union[str, Sequence[str], None] = '011d614e2802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type for admission_type
    admission_type_enum = sa.Enum(
        'GENERAL', 'LATERAL', 'TRANSFER', 'DIRECT', 'MANAGEMENT', 'COUNSELING',
        name='admissiontypeenum'
    )
    admission_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Add the admission_type column to admission_students table
    op.add_column(
        'admission_students',
        sa.Column('admission_type', admission_type_enum, nullable=True)
    )
    
    op.add_column(
        "admission_students",
        sa.Column("academic_year_id", sa.UUID(), sa.ForeignKey("academic_years.id"), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the admission_type column
    op.drop_column('admission_students', 'admission_type')
    
    # Drop the enum type
    admission_type_enum = sa.Enum(
        'GENERAL', 'LATERAL', 'TRANSFER', 'DIRECT', 'MANAGEMENT', 'COUNSELING',
        name='admissiontypeenum'
    )
    admission_type_enum.drop(op.get_bind(), checkfirst=True)
