"""Add fee structure lock fields to admission_students

Revision ID: 20260222_fee_lock_fields
Revises: 20260222_postadm_fields
Create Date: 2026-02-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260222_fee_lock_fields"
down_revision = "20260222_postadm_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admission_students",
        sa.Column("fee_structure_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "admission_students",
        sa.Column(
            "is_fee_structure_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "admission_students",
        sa.Column("fee_structure_locked_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "admission_students",
        sa.Column("fee_structure_locked_by", sa.UUID(), nullable=True),
    )

    op.create_index(
        "ix_admission_students_fee_structure_id",
        "admission_students",
        ["fee_structure_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_adm_students_fee_structure",
        "admission_students",
        "fee_structures",
        ["fee_structure_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_adm_students_fee_lock_user",
        "admission_students",
        "users",
        ["fee_structure_locked_by"],
        ["id"],
        initially="DEFERRED",
        deferrable=True,
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_adm_students_fee_lock_user", "admission_students", type_="foreignkey")
    op.drop_constraint("fk_adm_students_fee_structure", "admission_students", type_="foreignkey")
    op.drop_index("ix_admission_students_fee_structure_id", table_name="admission_students")

    op.drop_column("admission_students", "fee_structure_locked_by")
    op.drop_column("admission_students", "fee_structure_locked_at")
    op.drop_column("admission_students", "is_fee_structure_locked")
    op.drop_column("admission_students", "fee_structure_id")
