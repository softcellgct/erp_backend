"""Normalize admission status enum value PROVISIONALLY_ALLOTED -> PROVISIONALLY_ALLOTTED

Revision ID: 20260222_norm_prov_status
Revises: 0ee2223e893a
Create Date: 2026-02-22 00:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260222_norm_prov_status"
down_revision = "0ee2223e893a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
DO $$
DECLARE
    has_old_label boolean;
    has_new_label boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'admissionstatusenum'
          AND e.enumlabel = 'PROVISIONALLY_ALLOTED'
    ) INTO has_old_label;

    SELECT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'admissionstatusenum'
          AND e.enumlabel = 'PROVISIONALLY_ALLOTTED'
    ) INTO has_new_label;

    IF has_old_label AND NOT has_new_label THEN
        ALTER TYPE admissionstatusenum
        RENAME VALUE 'PROVISIONALLY_ALLOTED' TO 'PROVISIONALLY_ALLOTTED';
    ELSIF has_old_label AND has_new_label THEN
        ALTER TABLE admission_students ALTER COLUMN status DROP DEFAULT;

        ALTER TYPE admissionstatusenum RENAME TO admissionstatusenum_old;

        CREATE TYPE admissionstatusenum AS ENUM (
            'ENQUIRY',
            'ENQUIRED',
            'BOOKED',
            'APPLIED',
            'DOCUMENTS_PENDING',
            'DOCUMENTS_VERIFIED',
            'FEE_PENDING',
            'FEE_RECEIVED',
            'ADMISSION_GRANTED',
            'FORM_VERIFICATION_PENDING',
            'FORM_VERIFIED',
            'APPLICATION_RECEIVED',
            'PROVISIONALLY_ALLOTTED',
            'ENROLLED',
            'WAITLISTED',
            'REJECTED',
            'WITHDRAWN',
            'ON_HOLD'
        );

        ALTER TABLE admission_students
        ALTER COLUMN status TYPE admissionstatusenum
        USING (
            CASE
                WHEN status::text = 'PROVISIONALLY_ALLOTED' THEN 'PROVISIONALLY_ALLOTTED'
                ELSE status::text
            END
        )::admissionstatusenum;

        ALTER TABLE admission_students
        ALTER COLUMN status SET DEFAULT 'ENQUIRED'::admissionstatusenum;

        DROP TYPE admissionstatusenum_old;
    END IF;
END $$;
"""
    )


def downgrade() -> None:
    op.execute(
        """
DO $$
BEGIN
    ALTER TABLE admission_students ALTER COLUMN status DROP DEFAULT;

    ALTER TYPE admissionstatusenum RENAME TO admissionstatusenum_new;

    CREATE TYPE admissionstatusenum AS ENUM (
        'ENQUIRY',
        'ENQUIRED',
        'BOOKED',
        'APPLIED',
        'DOCUMENTS_PENDING',
        'DOCUMENTS_VERIFIED',
        'FEE_PENDING',
        'FEE_RECEIVED',
        'ADMISSION_GRANTED',
        'FORM_VERIFICATION_PENDING',
        'FORM_VERIFIED',
        'APPLICATION_RECEIVED',
        'PROVISIONALLY_ALLOTED',
        'ENROLLED',
        'WAITLISTED',
        'REJECTED',
        'WITHDRAWN',
        'ON_HOLD'
    );

    ALTER TABLE admission_students
    ALTER COLUMN status TYPE admissionstatusenum
    USING (
        CASE
            WHEN status::text = 'PROVISIONALLY_ALLOTTED' THEN 'PROVISIONALLY_ALLOTED'
            ELSE status::text
        END
    )::admissionstatusenum;

    ALTER TABLE admission_students
    ALTER COLUMN status SET DEFAULT 'ENQUIRED'::admissionstatusenum;

    DROP TYPE admissionstatusenum_new;
END $$;
"""
    )
