"""Add post-admission fields to admission_students

Revision ID: 20260222_postadm_fields
Revises: 20260222_add_adm_status, 20260222_uayi_inst
Create Date: 2026-02-22 01:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260222_postadm_fields"
down_revision = ("20260222_add_adm_status", "20260222_uayi_inst")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admission_students", sa.Column("roll_number", sa.String(length=50), nullable=True))
    op.add_column("admission_students", sa.Column("section", sa.String(length=20), nullable=True))
    op.add_column("admission_students", sa.Column("current_semester", sa.Integer(), nullable=True))
    op.add_column(
        "admission_students",
        sa.Column("is_sem1_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("admission_students", sa.Column("enrolled_at", sa.DateTime(), nullable=True))

    op.create_index(
        "ix_admission_students_roll_number",
        "admission_students",
        ["roll_number"],
        unique=False,
    )
    op.create_index(
        "ix_admission_students_section",
        "admission_students",
        ["section"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admission_students_section", table_name="admission_students")
    op.drop_index("ix_admission_students_roll_number", table_name="admission_students")

    op.drop_column("admission_students", "enrolled_at")
    op.drop_column("admission_students", "is_sem1_active")
    op.drop_column("admission_students", "current_semester")
    op.drop_column("admission_students", "section")
    op.drop_column("admission_students", "roll_number")
