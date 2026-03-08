"""Add payer_type, bulk_receipts tables for fee management architecture

Revision ID: fee_mgmt_payer_type_001
Revises: semester_scholarship_refund_001
Create Date: 2026-03-05

Changes:
1. Create payer_type_enum type
2. Add payer_type column to fee_structure_items
3. Add payer_type column to demand_items
4. Create bulk_receipts table
5. Create bulk_receipt_items table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "fee_mgmt_payer_type_001"
down_revision = "semester_scholarship_refund_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Create payer_type enum
    payer_type_enum = sa.Enum(
        "STUDENT", "GOVERNMENT", "SCHOLARSHIP",
        name="payer_type_enum",
    )
    payer_type_enum.create(bind, checkfirst=True)

    # 2. Add payer_type to fee_structure_items
    existing_columns = [c["name"] for c in inspector.get_columns("fee_structure_items")]
    if "payer_type" not in existing_columns:
        op.add_column(
            "fee_structure_items",
            sa.Column(
                "payer_type",
                sa.Enum("STUDENT", "GOVERNMENT", "SCHOLARSHIP", name="payer_type_enum", create_type=False),
                nullable=False,
                server_default="STUDENT",
            ),
        )

    # 3. Add payer_type to demand_items
    existing_columns = [c["name"] for c in inspector.get_columns("demand_items")]
    if "payer_type" not in existing_columns:
        op.add_column(
            "demand_items",
            sa.Column(
                "payer_type",
                sa.Enum("STUDENT", "GOVERNMENT", "SCHOLARSHIP", name="payer_type_enum", create_type=False),
                nullable=False,
                server_default="STUDENT",
            ),
        )

    # 4. Create bulk_receipts table
    existing_tables = inspector.get_table_names()
    if "bulk_receipts" not in existing_tables:
        op.create_table(
            "bulk_receipts",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("institution_id", UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column(
                "payer_type",
                sa.Enum("STUDENT", "GOVERNMENT", "SCHOLARSHIP", name="payer_type_enum", create_type=False),
                nullable=False,
                server_default="GOVERNMENT",
            ),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("reference_number", sa.String(200), nullable=False, unique=True, index=True),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="processed"),
            sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("amount > 0", name="ck_bulk_receipt_amount_positive"),
        )

    # 5. Create bulk_receipt_items table
    if "bulk_receipt_items" not in existing_tables:
        op.create_table(
            "bulk_receipt_items",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("bulk_receipt_id", UUID(as_uuid=True), sa.ForeignKey("bulk_receipts.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("amount > 0", name="ck_bulk_receipt_item_amount_positive"),
        )


def downgrade() -> None:
    op.drop_table("bulk_receipt_items")
    op.drop_table("bulk_receipts")
    op.drop_column("demand_items", "payer_type")
    op.drop_column("fee_structure_items", "payer_type")
    sa.Enum(name="payer_type_enum").drop(op.get_bind(), checkfirst=True)
