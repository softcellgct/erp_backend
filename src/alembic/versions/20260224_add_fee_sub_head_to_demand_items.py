"""Add fee_sub_head_id to demand_items

Revision ID: 20260224_demand_subhead
Revises: 20260222_merge_fee_vs_case
Create Date: 2026-02-24 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260224_demand_subhead"
down_revision = "20260222_merge_fee_vs_case"
branch_labels = None
depends_on = None


def _table_columns(inspector, table_name: str) -> set[str]:
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    try:
        return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))
    except Exception:
        return False


def _fk_exists(inspector, table_name: str, fk_name: str) -> bool:
    try:
        return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _table_columns(inspector, "demand_items")

    if "fee_sub_head_id" not in cols:
        op.add_column("demand_items", sa.Column("fee_sub_head_id", sa.UUID(), nullable=True))

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "demand_items", "ix_demand_items_fee_sub_head_id"):
        op.create_index(
            "ix_demand_items_fee_sub_head_id",
            "demand_items",
            ["fee_sub_head_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if not _fk_exists(inspector, "demand_items", "fk_demand_items_fee_sub_head_id"):
        op.create_foreign_key(
            "fk_demand_items_fee_sub_head_id",
            "demand_items",
            "fee_sub_heads",
            ["fee_sub_head_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _fk_exists(inspector, "demand_items", "fk_demand_items_fee_sub_head_id"):
        op.drop_constraint("fk_demand_items_fee_sub_head_id", "demand_items", type_="foreignkey")

    inspector = sa.inspect(bind)
    if _index_exists(inspector, "demand_items", "ix_demand_items_fee_sub_head_id"):
        op.drop_index("ix_demand_items_fee_sub_head_id", table_name="demand_items")

    cols = _table_columns(inspector, "demand_items")
    if "fee_sub_head_id" in cols:
        op.drop_column("demand_items", "fee_sub_head_id")
