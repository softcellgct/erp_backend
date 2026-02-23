"""Add missing admission status enum labels

Revision ID: 20260222_add_adm_status
Revises: 20260222_norm_prov_status
Create Date: 2026-02-22 00:45:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260222_add_adm_status"
down_revision = "20260222_norm_prov_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'admissionstatusenum'
          AND e.enumlabel = 'FORM_VERIFICATION_PENDING'
    ) THEN
        ALTER TYPE admissionstatusenum ADD VALUE 'FORM_VERIFICATION_PENDING';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'admissionstatusenum'
          AND e.enumlabel = 'FORM_VERIFIED'
    ) THEN
        ALTER TYPE admissionstatusenum ADD VALUE 'FORM_VERIFIED';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'admissionstatusenum'
          AND e.enumlabel = 'APPLICATION_RECEIVED'
    ) THEN
        ALTER TYPE admissionstatusenum ADD VALUE 'APPLICATION_RECEIVED';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'admissionstatusenum'
          AND e.enumlabel = 'PROVISIONALLY_ALLOTTED'
    ) THEN
        ALTER TYPE admissionstatusenum ADD VALUE 'PROVISIONALLY_ALLOTTED';
    END IF;
END $$;
"""
    )


def downgrade() -> None:
    # PostgreSQL does not support dropping enum labels safely in-place.
    # Intentionally left as no-op.
    pass
