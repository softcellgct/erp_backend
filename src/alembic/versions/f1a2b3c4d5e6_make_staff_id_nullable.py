"""make_staff_id_nullable

Revision ID: f1a2b3c4d5e6
Revises: e943424e905a
Create Date: 2026-02-26 08:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e943424e905a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Add column if it does not exist, otherwise make it nullable
    cols = [c["name"] for c in insp.get_columns("staff_references")]
    if "staff_id" not in cols:
        op.add_column(
            "staff_references",
            sa.Column("staff_id", sa.UUID(), nullable=True),
        )
    else:
        # If column exists, ensure it's nullable
        try:
            op.alter_column("staff_references", "staff_id", nullable=True, existing_type=sa.UUID())
        except Exception:
            # best-effort: if alter fails, continue
            pass

    # Create index if missing
    idxs = [i["name"] for i in insp.get_indexes("staff_references")]
    idx_name = op.f("ix_staff_references_staff_id")
    if idx_name not in idxs:
        op.create_index(idx_name, "staff_references", ["staff_id"], unique=False)

    # Create foreign key if missing (constrained_columns check)
    existing_fks = insp.get_foreign_keys("staff_references")
    has_fk = any(fk.get("constrained_columns") == ["staff_id"] for fk in existing_fks)
    if not has_fk:
        op.create_foreign_key(
            "fk_staff_references_staff_id_staff_members",
            "staff_references",
            "staff_members",
            ["staff_id"],
            ["id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Drop FK(s) that reference staff_id
    for fk in insp.get_foreign_keys("staff_references"):
        if fk.get("constrained_columns") == ["staff_id"]:
            try:
                op.drop_constraint(fk["name"], "staff_references", type_="foreignkey")
            except Exception:
                pass

    # Drop index if present
    idxs = [i["name"] for i in insp.get_indexes("staff_references")]
    idx_name = op.f("ix_staff_references_staff_id")
    if idx_name in idxs:
        try:
            op.drop_index(idx_name, table_name="staff_references")
        except Exception:
            pass

    # Drop column if present
    cols = [c["name"] for c in insp.get_columns("staff_references")]
    if "staff_id" in cols:
        try:
            op.drop_column("staff_references", "staff_id")
        except Exception:
            pass
