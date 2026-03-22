"""Add direct_admission to admission reference_type values

Revision ID: 20260320_ref_type_direct
Revises: 2ad28a0a3bf9
Create Date: 2026-03-20 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260320_ref_type_direct"
down_revision: Union[str, Sequence[str], None] = "2ad28a0a3bf9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_reference_type_checks() -> None:
    op.execute(
        """
        DO $$
        DECLARE constraint_name text;
        BEGIN
            FOR constraint_name IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE t.relname = 'admission_students'
                  AND n.nspname = current_schema()
                  AND c.contype = 'c'
                  AND pg_get_constraintdef(c.oid) ILIKE '%reference_type%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE admission_students DROP CONSTRAINT %I',
                    constraint_name
                );
            END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE admission_students "
        "ALTER COLUMN reference_type TYPE VARCHAR(100)"
    )

    _drop_reference_type_checks()

    op.create_check_constraint(
        "ck_admission_students_reference_type",
        "admission_students",
        "reference_type IS NULL OR reference_type IN ('consultancy', 'staff', 'student', 'other', 'direct_admission')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    _drop_reference_type_checks()

    op.execute(
        "UPDATE admission_students "
        "SET reference_type = 'other' "
        "WHERE reference_type = 'direct_admission'"
    )

    op.create_check_constraint(
        "ck_admission_students_reference_type",
        "admission_students",
        "reference_type IS NULL OR reference_type IN ('consultancy', 'staff', 'student', 'other')",
    )
