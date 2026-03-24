"""Add school context fields to multi_receipts

Revision ID: 20260324_multi_receipt_school
Revises: 20260324_school_district
Create Date: 2026-03-24 15:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260324_multi_receipt_school"
down_revision: Union[str, Sequence[str], None] = "20260324_school_district"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("multi_receipts")}
    if "school_master_id" not in columns:
        op.add_column("multi_receipts", sa.Column("school_master_id", sa.UUID(), nullable=True))
    if "school_name" not in columns:
        op.add_column("multi_receipts", sa.Column("school_name", sa.String(length=500), nullable=True))
    if "school_block" not in columns:
        op.add_column("multi_receipts", sa.Column("school_block", sa.String(length=200), nullable=True))
    if "school_district" not in columns:
        op.add_column("multi_receipts", sa.Column("school_district", sa.String(length=200), nullable=True))

    indexes = {idx["name"] for idx in inspector.get_indexes("multi_receipts")}
    if op.f("ix_multi_receipts_school_master_id") not in indexes:
        op.create_index(op.f("ix_multi_receipts_school_master_id"), "multi_receipts", ["school_master_id"], unique=False)

    fks = {fk["name"] for fk in inspector.get_foreign_keys("multi_receipts")}
    if "fk_multi_receipts_school_master_id" not in fks:
        op.create_foreign_key(
            "fk_multi_receipts_school_master_id",
            "multi_receipts",
            "school_master",
            ["school_master_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    fks = {fk["name"] for fk in inspector.get_foreign_keys("multi_receipts")}
    if "fk_multi_receipts_school_master_id" in fks:
        op.drop_constraint("fk_multi_receipts_school_master_id", "multi_receipts", type_="foreignkey")

    indexes = {idx["name"] for idx in inspector.get_indexes("multi_receipts")}
    if op.f("ix_multi_receipts_school_master_id") in indexes:
        op.drop_index(op.f("ix_multi_receipts_school_master_id"), table_name="multi_receipts")

    columns = {col["name"] for col in inspector.get_columns("multi_receipts")}
    if "school_district" in columns:
        op.drop_column("multi_receipts", "school_district")
    if "school_block" in columns:
        op.drop_column("multi_receipts", "school_block")
    if "school_name" in columns:
        op.drop_column("multi_receipts", "school_name")
    if "school_master_id" in columns:
        op.drop_column("multi_receipts", "school_master_id")
