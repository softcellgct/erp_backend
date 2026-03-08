"""Update student reference: remove course, add roll_number

Revision ID: student_ref_roll_number_001
Revises: fee_mgmt_payer_type_001
Create Date: 2026-03-08

Changes:
1. Drop course column from student_references table
2. Add roll_number column to student_references table
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "student_ref_roll_number_001"
down_revision = "fee_mgmt_payer_type_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    
    # Drop the course column
    op.drop_column("student_references", "course")
    
    # Add the roll_number column
    op.add_column(
        "student_references",
        sa.Column("roll_number", sa.String(255), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    
    # Drop roll_number column
    op.drop_column("student_references", "roll_number")
    
    # Re-add the course column
    op.add_column(
        "student_references",
        sa.Column("course", sa.String(255), nullable=False),
    )
