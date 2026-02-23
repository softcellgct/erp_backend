"""
Revision ID: 20260222_uayi_inst
Revises: f829991d211e
Create Date: 2026-02-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260222_uayi_inst"
down_revision = 'f829991d211e'
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


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    fy_cols = _table_columns(inspector, "financial_years")
    ay_cols = _table_columns(inspector, "academic_years")

    # Normalize existing duplicates before adding unique partial indexes.
    # Keep the most recently updated row active per institution; deactivate the rest.
    if {"id", "institution_id", "active"}.issubset(fy_cols):
        op.execute(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY institution_id
                           ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM financial_years
                WHERE active IS TRUE
            )
            UPDATE financial_years fy
            SET active = FALSE
            FROM ranked r
            WHERE fy.id = r.id
              AND r.rn > 1;
            """
        )

    if {"id", "institution_id", "status"}.issubset(ay_cols):
        op.execute(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY institution_id
                           ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM academic_years
                WHERE status IS TRUE
            )
            UPDATE academic_years ay
            SET status = FALSE
            FROM ranked r
            WHERE ay.id = r.id
              AND r.rn > 1;
            """
        )

    if {"id", "institution_id", "admission_active"}.issubset(ay_cols):
        op.execute(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY institution_id
                           ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM academic_years
                WHERE admission_active IS TRUE
            )
            UPDATE academic_years ay
            SET admission_active = FALSE
            FROM ranked r
            WHERE ay.id = r.id
              AND r.rn > 1;
            """
        )

    # Force deferred constraint triggers to fire before CREATE INDEX.
    # Without this, PostgreSQL can raise:
    # "cannot CREATE INDEX ... because it has pending trigger events"
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")

    # Financial years: only one active per institution
    if {"institution_id", "active"}.issubset(fy_cols) and not _index_exists(
        inspector, "financial_years", "ux_financial_years_active_per_institution"
    ):
        op.create_index(
            "ux_financial_years_active_per_institution",
            "financial_years",
            ["institution_id"],
            unique=True,
            postgresql_where=sa.text("active IS TRUE"),
        )

    # Academic years: only one status==True per institution
    if {"institution_id", "status"}.issubset(ay_cols) and not _index_exists(
        inspector, "academic_years", "ux_academic_years_status_active_per_institution"
    ):
        op.create_index(
            "ux_academic_years_status_active_per_institution",
            "academic_years",
            ["institution_id"],
            unique=True,
            postgresql_where=sa.text("status IS TRUE"),
        )

    # Academic years: only one admission_active==True per institution
    if {"institution_id", "admission_active"}.issubset(ay_cols) and not _index_exists(
        inspector, "academic_years", "ux_academic_years_admission_active_per_institution"
    ):
        op.create_index(
            "ux_academic_years_admission_active_per_institution",
            "academic_years",
            ["institution_id"],
            unique=True,
            postgresql_where=sa.text("admission_active IS TRUE"),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, "financial_years", "ux_financial_years_active_per_institution"):
        op.drop_index("ux_financial_years_active_per_institution", table_name="financial_years")
    if _index_exists(inspector, "academic_years", "ux_academic_years_status_active_per_institution"):
        op.drop_index("ux_academic_years_status_active_per_institution", table_name="academic_years")
    if _index_exists(inspector, "academic_years", "ux_academic_years_admission_active_per_institution"):
        op.drop_index("ux_academic_years_admission_active_per_institution", table_name="academic_years")
