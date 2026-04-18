"""Drop duplicated program columns from admission_students.

Revision ID: 20260417_drop_legacy_student_program
Revises: 20260416_defaults
Create Date: 2026-04-17 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260417_drop_legacy_student_program"
down_revision: Union[str, Sequence[str], None] = "20260416_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop legacy duplicated columns now stored in admission_student_program_details."""
    op.drop_column("admission_students", "academic_year_id")
    op.drop_column("admission_students", "admission_type_id")
    op.drop_column("admission_students", "admission_quota_id")
    op.drop_column("admission_students", "boarding_place")
    op.drop_column("admission_students", "scholarships")
    op.drop_column("admission_students", "special_quota")
    op.drop_column("admission_students", "quota_type")
    op.drop_column("admission_students", "category")


def downgrade() -> None:
    """Recreate legacy columns for rollback compatibility."""
    op.add_column(
        "admission_students",
        sa.Column("category", postgresql.ENUM("GENERAL", "OBC", "SC", "ST", "MBC", "DNC", "OTHERS", name="categoryenum"), nullable=True),
    )
    op.add_column("admission_students", sa.Column("quota_type", sa.String(length=50), nullable=True))
    op.add_column("admission_students", sa.Column("special_quota", sa.String(length=100), nullable=True))
    op.add_column("admission_students", sa.Column("scholarships", sa.String(length=200), nullable=True))
    op.add_column("admission_students", sa.Column("boarding_place", sa.String(length=200), nullable=True))
    op.add_column("admission_students", sa.Column("admission_quota_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("admission_students", sa.Column("admission_type_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("admission_students", sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_foreign_key(
        "admission_students_admission_quota_id_fkey",
        "admission_students",
        "seat_quotas",
        ["admission_quota_id"],
        ["id"],
    )
    op.create_foreign_key(
        "admission_students_admission_type_id_fkey",
        "admission_students",
        "admission_types",
        ["admission_type_id"],
        ["id"],
    )
    op.create_foreign_key(
        "admission_students_academic_year_id_fkey",
        "admission_students",
        "academic_years",
        ["academic_year_id"],
        ["id"],
    )

    op.create_index(op.f("ix_admission_students_admission_quota_id"), "admission_students", ["admission_quota_id"], unique=False)
    op.create_index(op.f("ix_admission_students_admission_type_id"), "admission_students", ["admission_type_id"], unique=False)
    op.create_index(op.f("ix_admission_students_academic_year_id"), "admission_students", ["academic_year_id"], unique=False)
