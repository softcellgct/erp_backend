"""Add admission visitor pass-out lifecycle fields

Revision ID: 20260222_adm_gate_out
Revises: 5bdc9b1a70e3
Create Date: 2026-02-22 12:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260222_adm_gate_out"
down_revision = "5bdc9b1a70e3"
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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _table_columns(inspector, "admission_visitors")

    if "visit_status" not in cols:
        op.add_column(
            "admission_visitors",
            sa.Column(
                "visit_status",
                sa.String(length=20),
                nullable=True,
                server_default=sa.text("'CHECKED_IN'"),
            ),
        )
    if "check_in_time" not in cols:
        op.add_column(
            "admission_visitors",
            sa.Column(
                "check_in_time",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.text("now()"),
            ),
        )
    if "check_out_time" not in cols:
        op.add_column(
            "admission_visitors",
            sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
        )
    if "check_out_remarks" not in cols:
        op.add_column(
            "admission_visitors",
            sa.Column("check_out_remarks", sa.String(length=255), nullable=True),
        )

    op.execute(
        """
        UPDATE admission_visitors
        SET visit_status = 'CHECKED_IN'
        WHERE visit_status IS NULL;
        """
    )
    op.execute(
        """
        UPDATE admission_visitors
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
    op.execute(
        """
        UPDATE admission_visitors
        SET check_in_time = COALESCE(check_in_time, created_at, now())
        WHERE check_in_time IS NULL;
        """
    )

    op.alter_column(
        "admission_visitors",
        "visit_status",
        nullable=False,
        existing_type=sa.String(length=20),
    )
    op.alter_column(
        "admission_visitors",
        "check_in_time",
        nullable=False,
        existing_type=sa.DateTime(timezone=True),
    )

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "admission_visitors", "ix_admission_visitors_visit_status"):
        op.create_index(
            "ix_admission_visitors_visit_status",
            "admission_visitors",
            ["visit_status"],
            unique=False,
        )
    if not _index_exists(inspector, "admission_visitors", "ix_admission_visitors_check_in_time"):
        op.create_index(
            "ix_admission_visitors_check_in_time",
            "admission_visitors",
            ["check_in_time"],
            unique=False,
        )
    if not _index_exists(inspector, "admission_visitors", "ix_admission_visitors_check_out_time"):
        op.create_index(
            "ix_admission_visitors_check_out_time",
            "admission_visitors",
            ["check_out_time"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, "admission_visitors", "ix_admission_visitors_check_out_time"):
        op.drop_index("ix_admission_visitors_check_out_time", table_name="admission_visitors")
    if _index_exists(inspector, "admission_visitors", "ix_admission_visitors_check_in_time"):
        op.drop_index("ix_admission_visitors_check_in_time", table_name="admission_visitors")
    if _index_exists(inspector, "admission_visitors", "ix_admission_visitors_visit_status"):
        op.drop_index("ix_admission_visitors_visit_status", table_name="admission_visitors")

    cols = _table_columns(inspector, "admission_visitors")
    if "check_out_remarks" in cols:
        op.drop_column("admission_visitors", "check_out_remarks")
    if "check_out_time" in cols:
        op.drop_column("admission_visitors", "check_out_time")
    if "check_in_time" in cols:
        op.drop_column("admission_visitors", "check_in_time")
    if "visit_status" in cols:
        op.drop_column("admission_visitors", "visit_status")
