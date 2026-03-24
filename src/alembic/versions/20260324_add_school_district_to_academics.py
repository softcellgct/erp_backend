"""Add school_district to SSLC and HSC details

Revision ID: 20260324_school_district
Revises: 20260322_multi_receipts
Create Date: 2026-03-24 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260324_school_district"
down_revision: Union[str, Sequence[str], None] = "20260322_multi_receipts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_column("sslc_details", "school_district"):
        op.add_column("sslc_details", sa.Column("school_district", sa.String(length=200), nullable=True))

    if not _has_column("hsc_details", "school_district"):
        op.add_column("hsc_details", sa.Column("school_district", sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if _has_column("hsc_details", "school_district"):
        op.drop_column("hsc_details", "school_district")

    if _has_column("sslc_details", "school_district"):
        op.drop_column("sslc_details", "school_district")
