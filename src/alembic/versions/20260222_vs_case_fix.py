"""Normalize visit_status casing for gate visitors

Revision ID: 20260222_vs_case_fix
Revises: 20260222_adm_gate_out
Create Date: 2026-02-22 13:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260222_vs_case_fix"
down_revision = "20260222_adm_gate_out"
branch_labels = None
depends_on = None


def _table_columns(inspector, table_name: str) -> set[str]:
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def _normalize_visit_status(table_name: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET visit_status = CASE lower(trim(visit_status))
            WHEN 'pending' THEN 'PENDING'
            WHEN 'checked_in' THEN 'CHECKED_IN'
            WHEN 'checked_out' THEN 'CHECKED_OUT'
            WHEN 'cancelled' THEN 'CANCELLED'
            ELSE visit_status
        END
        WHERE visit_status IS NOT NULL;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    admission_cols = _table_columns(inspector, "admission_visitors")
    if "visit_status" in admission_cols:
        _normalize_visit_status("admission_visitors")
        op.alter_column(
            "admission_visitors",
            "visit_status",
            server_default=sa.text("'CHECKED_IN'"),
            existing_type=sa.String(length=20),
            existing_nullable=False,
        )

    visitor_cols = _table_columns(inspector, "visitors")
    if "visit_status" in visitor_cols:
        _normalize_visit_status("visitors")


def downgrade() -> None:
    # Intentionally a no-op. This migration is corrective data normalization.
    pass
