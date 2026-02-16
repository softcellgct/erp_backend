"""update_defaults_and_simplify_certificates

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-16 10:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Now that enum values are committed, we can update the default
    op.alter_column('admission_students', 'status',
                    server_default='ENQUIRED',
                    existing_nullable=False)
    
    # Check if foreign key constraints exist before dropping
    # Drop foreign key constraints from admission_required_certificates
    try:
        op.drop_constraint('admission_required_certificates_academic_year_id_fkey', 
                          'admission_required_certificates', type_='foreignkey')
    except Exception:
        pass  # Constraint might not exist
        
    try:
        op.drop_constraint('admission_required_certificates_department_id_fkey', 
                          'admission_required_certificates', type_='foreignkey')
    except Exception:
        pass  # Constraint might not exist
    
    # Check if columns exist before dropping
    try:
        op.drop_column('admission_required_certificates', 'academic_year_id')
    except Exception:
        pass  # Column might not exist
        
    try:
        op.drop_column('admission_required_certificates', 'department_id')
    except Exception:
        pass  # Column might not exist


def downgrade():
    # Add back the columns
    op.add_column('admission_required_certificates',
                 sa.Column('department_id', postgresql.UUID(), nullable=True))
    op.add_column('admission_required_certificates',
                 sa.Column('academic_year_id', postgresql.UUID(), nullable=True))
    
    # Re-add foreign key constraints
    op.create_foreign_key('admission_required_certificates_department_id_fkey',
                         'admission_required_certificates', 'departments',
                         ['department_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('admission_required_certificates_academic_year_id_fkey',
                         'admission_required_certificates', 'academic_years',
                         ['academic_year_id'], ['id'], ondelete='CASCADE')
    
    # Revert default status
    op.alter_column('admission_students', 'status',
                    server_default='APPLIED',
                    existing_nullable=False)
