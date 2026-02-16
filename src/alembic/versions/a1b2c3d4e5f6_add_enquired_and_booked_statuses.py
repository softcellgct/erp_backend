"""add_enquired_and_booked_enum_values

Revision ID: a1b2c3d4e5f6
Revises: bb7103d7b9e6
Create Date: 2026-02-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'bb7103d7b9e6'
branch_labels = None
depends_on = None


def upgrade():
    # Enum values must be added manually first using add_enum_values.sql
    # This is due to asyncpg requiring enum values to be committed before use
    
    # Verify enum values exist
    from sqlalchemy import text
    conn = op.get_bind()
    
    result = conn.execute(text(
        "SELECT enumlabel FROM pg_type t "
        "JOIN pg_enum e ON t.oid = e.enumtypid "
        "WHERE t.typname = 'admissionstatusenum' AND e.enumlabel IN ('ENQUIRED', 'BOOKED')"
    ))
    values = [row[0] for row in result]
    
    if 'ENQUIRED' not in values or 'BOOKED' not in values:
        raise Exception(
            "ERROR: ENQUIRED and BOOKED enum values not found. "
            "Please run add_enum_values.sql first:\n"
            "psql -U <username> -d <database> -f add_enum_values.sql"
        )
    
    print("✓ Enum values ENQUIRED and BOOKED are present")


def downgrade():
    # Note: Removing enum values in PostgreSQL is very complex
    # We'll leave them in place but they won't be used
    print("Note: Enum values ENQUIRED and BOOKED will remain in the database")
    print("Removing them requires recreating the entire enum type which is not safe")
    pass
