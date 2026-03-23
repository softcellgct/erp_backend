"""Add multi_receipts and multi_receipt_items tables

Revision ID: 20260322_multi_receipts
Revises: 20260320_ref_type_direct
Create Date: 2026-03-22 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260322_multi_receipts"
down_revision: Union[str, Sequence[str], None] = "20260320_ref_type_direct"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("multi_receipts"):
        op.create_table(
            "multi_receipts",
            sa.Column("institution_id", sa.UUID(), nullable=False),
            sa.Column("fee_head_id", sa.UUID(), nullable=True),
            sa.Column("fee_sub_head_id", sa.UUID(), nullable=True),
            sa.Column(
                "payer_type",
                postgresql.ENUM(
                    "STUDENT",
                    "GOVERNMENT",
                    "SCHOLARSHIP",
                    name="payer_type_enum",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("receipt_number", sa.String(length=120), nullable=False),
            sa.Column("amount_per_student", sa.Numeric(12, 2), nullable=False),
            sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("student_count", sa.Integer(), nullable=False),
            sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("created_by", sa.UUID(), nullable=True),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_by", sa.UUID(), nullable=True),
            sa.Column("deleted_by", sa.UUID(), nullable=True),
            sa.CheckConstraint("amount_per_student > 0", name="ck_multi_receipt_amount_per_student_positive"),
            sa.CheckConstraint("total_amount > 0", name="ck_multi_receipt_total_amount_positive"),
            sa.CheckConstraint("student_count >= 0", name="ck_multi_receipt_student_count_non_negative"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["fee_head_id"], ["fee_heads.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["fee_sub_head_id"], ["fee_sub_heads.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_multi_receipt_indexes = {idx["name"] for idx in inspector.get_indexes("multi_receipts")}
    if op.f("ix_multi_receipts_id") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_id"), "multi_receipts", ["id"], unique=False)
    if op.f("ix_multi_receipts_created_at") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_created_at"), "multi_receipts", ["created_at"], unique=False)
    if op.f("ix_multi_receipts_updated_at") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_updated_at"), "multi_receipts", ["updated_at"], unique=False)
    if op.f("ix_multi_receipts_deleted_at") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_deleted_at"), "multi_receipts", ["deleted_at"], unique=False)
    if op.f("ix_multi_receipts_institution_id") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_institution_id"), "multi_receipts", ["institution_id"], unique=False)
    if op.f("ix_multi_receipts_fee_head_id") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_fee_head_id"), "multi_receipts", ["fee_head_id"], unique=False)
    if op.f("ix_multi_receipts_fee_sub_head_id") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_fee_sub_head_id"), "multi_receipts", ["fee_sub_head_id"], unique=False)
    if op.f("ix_multi_receipts_receipt_number") not in existing_multi_receipt_indexes:
        op.create_index(op.f("ix_multi_receipts_receipt_number"), "multi_receipts", ["receipt_number"], unique=True)

    if not inspector.has_table("multi_receipt_items"):
        op.create_table(
            "multi_receipt_items",
            sa.Column("multi_receipt_id", sa.UUID(), nullable=False),
            sa.Column("student_id", sa.UUID(), nullable=False),
            sa.Column("demand_item_id", sa.UUID(), nullable=True),
            sa.Column("invoice_id", sa.UUID(), nullable=True),
            sa.Column("payment_id", sa.UUID(), nullable=True),
            sa.Column("demanded_amount_before", sa.Numeric(12, 2), nullable=False),
            sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("demanded_amount_after", sa.Numeric(12, 2), nullable=False),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.UUID(), nullable=True),
            sa.Column("updated_by", sa.UUID(), nullable=True),
            sa.Column("deleted_by", sa.UUID(), nullable=True),
            sa.CheckConstraint("paid_amount >= 0", name="ck_multi_receipt_item_paid_non_negative"),
            sa.CheckConstraint("demanded_amount_before >= 0", name="ck_multi_receipt_item_before_non_negative"),
            sa.CheckConstraint("demanded_amount_after >= 0", name="ck_multi_receipt_item_after_non_negative"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["multi_receipt_id"], ["multi_receipts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["admission_students.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["demand_item_id"], ["demand_items.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_multi_receipt_item_indexes = {idx["name"] for idx in inspector.get_indexes("multi_receipt_items")}
    if op.f("ix_multi_receipt_items_id") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_id"), "multi_receipt_items", ["id"], unique=False)
    if op.f("ix_multi_receipt_items_created_at") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_created_at"), "multi_receipt_items", ["created_at"], unique=False)
    if op.f("ix_multi_receipt_items_updated_at") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_updated_at"), "multi_receipt_items", ["updated_at"], unique=False)
    if op.f("ix_multi_receipt_items_deleted_at") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_deleted_at"), "multi_receipt_items", ["deleted_at"], unique=False)
    if op.f("ix_multi_receipt_items_multi_receipt_id") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_multi_receipt_id"), "multi_receipt_items", ["multi_receipt_id"], unique=False)
    if op.f("ix_multi_receipt_items_student_id") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_student_id"), "multi_receipt_items", ["student_id"], unique=False)
    if op.f("ix_multi_receipt_items_demand_item_id") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_demand_item_id"), "multi_receipt_items", ["demand_item_id"], unique=False)
    if op.f("ix_multi_receipt_items_invoice_id") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_invoice_id"), "multi_receipt_items", ["invoice_id"], unique=False)
    if op.f("ix_multi_receipt_items_payment_id") not in existing_multi_receipt_item_indexes:
        op.create_index(op.f("ix_multi_receipt_items_payment_id"), "multi_receipt_items", ["payment_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("multi_receipt_items"):
        existing_item_indexes = {idx["name"] for idx in inspector.get_indexes("multi_receipt_items")}
        if op.f("ix_multi_receipt_items_payment_id") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_payment_id"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_invoice_id") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_invoice_id"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_demand_item_id") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_demand_item_id"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_student_id") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_student_id"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_multi_receipt_id") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_multi_receipt_id"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_deleted_at") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_deleted_at"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_updated_at") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_updated_at"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_created_at") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_created_at"), table_name="multi_receipt_items")
        if op.f("ix_multi_receipt_items_id") in existing_item_indexes:
            op.drop_index(op.f("ix_multi_receipt_items_id"), table_name="multi_receipt_items")
        op.drop_table("multi_receipt_items")

    if inspector.has_table("multi_receipts"):
        existing_receipt_indexes = {idx["name"] for idx in inspector.get_indexes("multi_receipts")}
        if op.f("ix_multi_receipts_receipt_number") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_receipt_number"), table_name="multi_receipts")
        if op.f("ix_multi_receipts_fee_sub_head_id") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_fee_sub_head_id"), table_name="multi_receipts")
        if op.f("ix_multi_receipts_fee_head_id") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_fee_head_id"), table_name="multi_receipts")
        if op.f("ix_multi_receipts_institution_id") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_institution_id"), table_name="multi_receipts")
        if op.f("ix_multi_receipts_deleted_at") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_deleted_at"), table_name="multi_receipts")
        if op.f("ix_multi_receipts_updated_at") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_updated_at"), table_name="multi_receipts")
        if op.f("ix_multi_receipts_created_at") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_created_at"), table_name="multi_receipts")
        if op.f("ix_multi_receipts_id") in existing_receipt_indexes:
            op.drop_index(op.f("ix_multi_receipts_id"), table_name="multi_receipts")
        op.drop_table("multi_receipts")
