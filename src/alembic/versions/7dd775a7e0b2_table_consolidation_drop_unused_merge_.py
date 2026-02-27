"""table_consolidation_drop_unused_merge_visitors_certs

Revision ID: 7dd775a7e0b2
Revises: 92b3da52483d
Create Date: 2026-02-25 15:41:10.118116

This migration:
  1. Adds gate-visit columns to admission_students (source, image_url,
     native_place, visit_status, check_in_time, check_out_time, check_out_remarks)
  2. Migrates data from admission_visitors → admission_students
  3. Re-points reference tables (consultancy/staff/student/other_references)
     from admission_visitors → admission_students
  4. Re-points submitted_certificates FK from admission_required_certificates
     → document_types
  5. Drops unused tables: permissions, user_permissions, vendor_visitors,
     admission_visitors, admission_required_certificates
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '7dd775a7e0b2'
down_revision: Union[str, Sequence[str], None] = '92b3da52483d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Drop completely unused tables (no data to migrate)
    # ------------------------------------------------------------------
    op.drop_index('ix_user_permissions_deleted_at', table_name='user_permissions')
    op.drop_index('ix_user_permissions_screen_id', table_name='user_permissions')
    op.drop_index('ix_user_permissions_user_id', table_name='user_permissions')
    op.drop_table('user_permissions')

    op.drop_index('ix_permissions_deleted_at', table_name='permissions')
    op.drop_index('ix_permissions_key', table_name='permissions')
    op.drop_table('permissions')

    op.drop_index('ix_vendor_visitors_deleted_at', table_name='vendor_visitors')
    op.drop_table('vendor_visitors')

    # ------------------------------------------------------------------
    # 2. Add new columns to admission_students (nullable first)
    # ------------------------------------------------------------------
    # source – existing rows default to DIRECT_ENTRY
    op.add_column(
        'admission_students',
        sa.Column(
            'source',
            sa.Enum('GATE_ENQUIRY', 'DIRECT_ENTRY', 'COUNSELING', name='sourceenum'),
            nullable=True,
        ),
    )
    op.execute("UPDATE admission_students SET source = 'DIRECT_ENTRY' WHERE source IS NULL")
    op.alter_column('admission_students', 'source', nullable=False)

    op.add_column('admission_students', sa.Column('image_url', sa.String(500), nullable=True))
    op.add_column('admission_students', sa.Column('native_place', sa.String(255), nullable=True))
    op.add_column(
        'admission_students',
        sa.Column(
            'visit_status',
            sa.Enum('PENDING', 'CHECKED_IN', 'CHECKED_OUT', 'CANCELLED', name='visitstatusenum'),
            nullable=True,
        ),
    )
    op.add_column('admission_students', sa.Column('check_in_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('admission_students', sa.Column('check_out_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('admission_students', sa.Column('check_out_remarks', sa.String(255), nullable=True))

    # ------------------------------------------------------------------
    # 3. Migrate admission_visitors rows → admission_students
    #    Step A: Update existing students that match a visitor by aadhaar
    #    Step B: Insert visitors that have no matching student at all
    # ------------------------------------------------------------------
    # A. Update existing students whose aadhaar matches a visitor
    op.execute("""
        UPDATE admission_students s
        SET source         = 'GATE_ENQUIRY'::sourceenum,
            image_url      = COALESCE(s.image_url, av.image_url),
            native_place   = COALESCE(s.native_place, av.native_place),
            gate_pass_number = COALESCE(s.gate_pass_number, av.gate_pass_no),
            reference_type = COALESCE(s.reference_type, av.reference_type),
            visit_status   = av.visit_status::visitstatusenum,
            check_in_time  = av.check_in_time,
            check_out_time = av.check_out_time,
            check_out_remarks = av.check_out_remarks
        FROM admission_visitors av
        WHERE s.aadhaar_number = av.aadhar_number
    """)

    # B. Insert visitors whose aadhaar doesn't match any existing student
    op.execute("""
        INSERT INTO admission_students (
            id, created_at, updated_at, deleted_at,
            created_by, updated_by, deleted_by,
            institution_id, status, source,
            name, student_mobile, father_name,
            aadhaar_number, native_place, image_url,
            gate_pass_number, reference_type,
            has_vehicle, vehicle_number,
            visit_status, check_in_time, check_out_time, check_out_remarks,
            enquiry_number
        )
        SELECT
            av.id, av.created_at, av.updated_at, av.deleted_at,
            av.created_by, av.updated_by, av.deleted_by,
            av.institution_id,
            av.status::admissionstatusenum,
            'GATE_ENQUIRY'::sourceenum,
            av.student_name, av.mobile_number, av.parent_or_guardian_name,
            av.aadhar_number, av.native_place, av.image_url,
            av.gate_pass_no, av.reference_type,
            av.vehicle, av.vehicle_number,
            av.visit_status::visitstatusenum,
            av.check_in_time, av.check_out_time, av.check_out_remarks,
            av.gate_pass_no
        FROM admission_visitors av
        WHERE NOT EXISTS (
            SELECT 1 FROM admission_students s
            WHERE s.id = av.id OR s.aadhaar_number = av.aadhar_number
        )
    """)

    # ------------------------------------------------------------------
    # 4. Re-point consultancy_references  (admission_visitor_id → student_id)
    #    For visitors that were UPDATE'd (matched by aadhaar), the student_id
    #    is the admission_student.id, not the old admission_visitor.id.
    # ------------------------------------------------------------------
    op.add_column('consultancy_references', sa.Column('student_id', sa.UUID(), nullable=True))
    # First try direct ID match (visitor was INSERT'd with same ID)
    op.execute("""
        UPDATE consultancy_references cr
        SET student_id = cr.admission_visitor_id
        WHERE EXISTS (SELECT 1 FROM admission_students s WHERE s.id = cr.admission_visitor_id)
    """)
    # Then match via aadhaar for visitors that were UPDATE'd onto existing students
    op.execute("""
        UPDATE consultancy_references cr
        SET student_id = s.id
        FROM admission_visitors av
        JOIN admission_students s ON s.aadhaar_number = av.aadhar_number
        WHERE cr.admission_visitor_id = av.id AND cr.student_id IS NULL
    """)
    # Delete orphans that couldn't be mapped
    op.execute("DELETE FROM consultancy_references WHERE student_id IS NULL")
    # Deduplicate: keep only the latest row per student_id
    op.execute("""
        DELETE FROM consultancy_references
        WHERE id NOT IN (
            SELECT DISTINCT ON (student_id) id
            FROM consultancy_references
            ORDER BY student_id, created_at DESC
        )
    """)
    op.alter_column('consultancy_references', 'student_id', nullable=False)
    op.drop_constraint('consultancy_references_admission_visitor_id_key', 'consultancy_references', type_='unique')
    op.drop_constraint('consultancy_references_admission_visitor_id_fkey', 'consultancy_references', type_='foreignkey')
    op.create_index('ix_consultancy_references_student_id', 'consultancy_references', ['student_id'], unique=True)
    op.create_foreign_key(None, 'consultancy_references', 'admission_students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_column('consultancy_references', 'admission_visitor_id')

    # ------------------------------------------------------------------
    # 5. Re-point other_references  (reference_id → student_id)
    # ------------------------------------------------------------------
    op.add_column('other_references', sa.Column('student_id', sa.UUID(), nullable=True))
    op.execute("""
        UPDATE other_references r
        SET student_id = r.reference_id
        WHERE EXISTS (SELECT 1 FROM admission_students s WHERE s.id = r.reference_id)
    """)
    op.execute("""
        UPDATE other_references r
        SET student_id = s.id
        FROM admission_visitors av
        JOIN admission_students s ON s.aadhaar_number = av.aadhar_number
        WHERE r.reference_id = av.id AND r.student_id IS NULL
    """)
    op.execute("DELETE FROM other_references WHERE student_id IS NULL")
    op.execute("""
        DELETE FROM other_references
        WHERE id NOT IN (
            SELECT DISTINCT ON (student_id) id
            FROM other_references
            ORDER BY student_id, created_at DESC
        )
    """)
    op.alter_column('other_references', 'student_id', nullable=False)
    op.drop_index('ix_other_references_reference_id', table_name='other_references')
    op.drop_constraint('other_references_reference_id_fkey', 'other_references', type_='foreignkey')
    op.create_index('ix_other_references_student_id', 'other_references', ['student_id'], unique=True)
    op.create_foreign_key(None, 'other_references', 'admission_students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_column('other_references', 'reference_id')

    # ------------------------------------------------------------------
    # 6. Re-point staff_references  (reference_id → student_id)
    # ------------------------------------------------------------------
    op.add_column('staff_references', sa.Column('student_id', sa.UUID(), nullable=True))
    op.execute("""
        UPDATE staff_references r
        SET student_id = r.reference_id
        WHERE EXISTS (SELECT 1 FROM admission_students s WHERE s.id = r.reference_id)
    """)
    op.execute("""
        UPDATE staff_references r
        SET student_id = s.id
        FROM admission_visitors av
        JOIN admission_students s ON s.aadhaar_number = av.aadhar_number
        WHERE r.reference_id = av.id AND r.student_id IS NULL
    """)
    op.execute("DELETE FROM staff_references WHERE student_id IS NULL")
    op.execute("""
        DELETE FROM staff_references
        WHERE id NOT IN (
            SELECT DISTINCT ON (student_id) id
            FROM staff_references
            ORDER BY student_id, created_at DESC
        )
    """)
    op.alter_column('staff_references', 'student_id', nullable=False)
    op.drop_index('ix_staff_references_reference_id', table_name='staff_references')
    op.drop_constraint('staff_references_reference_id_fkey', 'staff_references', type_='foreignkey')
    op.create_index('ix_staff_references_student_id', 'staff_references', ['student_id'], unique=True)
    op.create_foreign_key(None, 'staff_references', 'admission_students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_column('staff_references', 'reference_id')

    # ------------------------------------------------------------------
    # 7. Re-point student_references  (reference_id → student_id)
    # ------------------------------------------------------------------
    op.add_column('student_references', sa.Column('student_id', sa.UUID(), nullable=True))
    op.execute("""
        UPDATE student_references r
        SET student_id = r.reference_id
        WHERE EXISTS (SELECT 1 FROM admission_students s WHERE s.id = r.reference_id)
    """)
    op.execute("""
        UPDATE student_references r
        SET student_id = s.id
        FROM admission_visitors av
        JOIN admission_students s ON s.aadhaar_number = av.aadhar_number
        WHERE r.reference_id = av.id AND r.student_id IS NULL
    """)
    op.execute("DELETE FROM student_references WHERE student_id IS NULL")
    op.execute("""
        DELETE FROM student_references
        WHERE id NOT IN (
            SELECT DISTINCT ON (student_id) id
            FROM student_references
            ORDER BY student_id, created_at DESC
        )
    """)
    op.alter_column('student_references', 'student_id', nullable=False)
    op.drop_index('ix_student_references_reference_id', table_name='student_references')
    op.drop_constraint('student_references_reference_id_fkey', 'student_references', type_='foreignkey')
    op.create_index('ix_student_references_student_id', 'student_references', ['student_id'], unique=True)
    op.create_foreign_key(None, 'student_references', 'admission_students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_column('student_references', 'reference_id')

    # ------------------------------------------------------------------
    # 8. Re-point submitted_certificates (required_certificate_id → document_type_id)
    #    Map through the old admission_required_certificates table before dropping it.
    # ------------------------------------------------------------------
    op.add_column('submitted_certificates', sa.Column('document_type_id', sa.UUID(), nullable=True))
    op.execute("""
        UPDATE submitted_certificates sc
        SET document_type_id = arc.document_type_id
        FROM admission_required_certificates arc
        WHERE sc.required_certificate_id = arc.id
    """)
    # Any orphans that couldn't be mapped — set to NULL (shouldn't happen)
    op.alter_column('submitted_certificates', 'document_type_id', nullable=False)
    op.drop_index('ix_submitted_certificates_required_certificate_id', table_name='submitted_certificates')
    op.drop_constraint('submitted_certificates_required_certificate_id_fkey', 'submitted_certificates', type_='foreignkey')
    op.create_index('ix_submitted_certificates_document_type_id', 'submitted_certificates', ['document_type_id'], unique=False)
    op.create_foreign_key(None, 'submitted_certificates', 'document_types', ['document_type_id'], ['id'], ondelete='CASCADE')
    op.drop_column('submitted_certificates', 'required_certificate_id')

    # ------------------------------------------------------------------
    # 9. Now safe to drop the merged tables
    # ------------------------------------------------------------------
    op.drop_index('ix_admission_visitors_deleted_at', table_name='admission_visitors')
    op.drop_index('ix_admission_visitors_institution_id', table_name='admission_visitors')
    op.drop_table('admission_visitors')

    op.drop_index('ix_admission_required_certificates_deleted_at', table_name='admission_required_certificates')
    op.drop_index('ix_admission_required_certificates_document_type_id', table_name='admission_required_certificates')
    op.drop_table('admission_required_certificates')


def downgrade() -> None:
    """Best-effort downgrade — data migrated into admission_students cannot be
    perfectly un-merged, but the schema will be restored."""

    # Recreate admission_required_certificates
    op.create_table('admission_required_certificates',
        sa.Column('document_type_id', sa.UUID(), nullable=False),
        sa.Column('is_mandatory', sa.BOOLEAN(), nullable=False),
        sa.Column('description', sa.VARCHAR(500), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['document_type_id'], ['document_types.id'], name='admission_required_certificates_document_type_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='admission_required_certificates_pkey'),
    )
    op.create_index('ix_admission_required_certificates_document_type_id', 'admission_required_certificates', ['document_type_id'])
    op.create_index('ix_admission_required_certificates_deleted_at', 'admission_required_certificates', ['deleted_at'])

    # Recreate admission_visitors
    op.create_table('admission_visitors',
        sa.Column('gate_pass_no', sa.VARCHAR(50), nullable=False),
        sa.Column('student_name', sa.VARCHAR(255), nullable=False),
        sa.Column('mobile_number', sa.VARCHAR(), nullable=False),
        sa.Column('parent_or_guardian_name', sa.VARCHAR(255), nullable=False),
        sa.Column('aadhar_number', sa.VARCHAR(), nullable=False),
        sa.Column('native_place', sa.VARCHAR(255), nullable=False),
        sa.Column('image_url', sa.VARCHAR(), nullable=False),
        sa.Column('reference_type', sa.VARCHAR(11), nullable=False),
        sa.Column('vehicle', sa.BOOLEAN(), nullable=False),
        sa.Column('vehicle_number', sa.VARCHAR(50), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.Column('institution_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.VARCHAR(25), server_default=sa.text("'APPLIED'::character varying"), nullable=False),
        sa.Column('visit_status', sa.VARCHAR(11), server_default=sa.text("'CHECKED_IN'::character varying"), nullable=False),
        sa.Column('check_in_time', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('check_out_time', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('check_out_remarks', sa.VARCHAR(255), nullable=True),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name='fk_admission_visitors_institution_id'),
        sa.PrimaryKeyConstraint('id', name='admission_visitors_pkey'),
        sa.UniqueConstraint('gate_pass_no', name='admission_visitors_gate_pass_no_key'),
    )
    op.create_index('ix_admission_visitors_institution_id', 'admission_visitors', ['institution_id'])
    op.create_index('ix_admission_visitors_deleted_at', 'admission_visitors', ['deleted_at'])

    # Recreate vendor_visitors
    op.create_table('vendor_visitors',
        sa.Column('visitor_id', sa.UUID(), nullable=False),
        sa.Column('company_name', sa.VARCHAR(255), nullable=False),
        sa.Column('company_address', sa.TEXT(), nullable=True),
        sa.Column('company_contact', sa.VARCHAR(20), nullable=True),
        sa.Column('designation', sa.VARCHAR(100), nullable=True),
        sa.Column('carrying_materials', sa.BOOLEAN(), nullable=False),
        sa.Column('material_description', sa.TEXT(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['visitor_id'], ['visitors.id'], name='vendor_visitors_visitor_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='vendor_visitors_pkey'),
        sa.UniqueConstraint('visitor_id', name='vendor_visitors_visitor_id_key'),
    )
    op.create_index('ix_vendor_visitors_deleted_at', 'vendor_visitors', ['deleted_at'])

    # Recreate permissions
    op.create_table('permissions',
        sa.Column('key', sa.VARCHAR(255), nullable=False),
        sa.Column('path', sa.VARCHAR(255), nullable=False),
        sa.Column('method', sa.VARCHAR(10), nullable=False),
        sa.Column('description', sa.VARCHAR(255), nullable=False),
        sa.Column('tag', sa.VARCHAR(50), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='permissions_pkey'),
        sa.UniqueConstraint('key', name='permissions_key_key'),
    )
    op.create_index('ix_permissions_key', 'permissions', ['key'])
    op.create_index('ix_permissions_deleted_at', 'permissions', ['deleted_at'])

    # Recreate user_permissions
    op.create_table('user_permissions',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('screen_id', sa.UUID(), nullable=False),
        sa.Column('can_view', sa.BOOLEAN(), nullable=False),
        sa.Column('can_create', sa.BOOLEAN(), nullable=False),
        sa.Column('can_edit', sa.BOOLEAN(), nullable=False),
        sa.Column('can_delete', sa.BOOLEAN(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['screen_id'], ['screens.id'], name='user_permissions_screen_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_permissions_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='user_permissions_pkey'),
    )
    op.create_index('ix_user_permissions_user_id', 'user_permissions', ['user_id'])
    op.create_index('ix_user_permissions_screen_id', 'user_permissions', ['screen_id'])
    op.create_index('ix_user_permissions_deleted_at', 'user_permissions', ['deleted_at'])

    # Reverse submitted_certificates  (document_type_id → required_certificate_id)
    op.add_column('submitted_certificates', sa.Column('required_certificate_id', sa.UUID(), nullable=True))
    op.drop_constraint(None, 'submitted_certificates', type_='foreignkey')
    op.drop_index('ix_submitted_certificates_document_type_id', table_name='submitted_certificates')
    op.create_foreign_key('submitted_certificates_required_certificate_id_fkey', 'submitted_certificates', 'admission_required_certificates', ['required_certificate_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_submitted_certificates_required_certificate_id', 'submitted_certificates', ['required_certificate_id'])
    op.drop_column('submitted_certificates', 'document_type_id')

    # Reverse reference tables
    for table, old_col, old_fk_name in [
        ('student_references', 'reference_id', 'student_references_reference_id_fkey'),
        ('staff_references', 'reference_id', 'staff_references_reference_id_fkey'),
        ('other_references', 'reference_id', 'other_references_reference_id_fkey'),
    ]:
        op.add_column(table, sa.Column(old_col, sa.UUID(), nullable=True))
        op.execute(f"UPDATE {table} SET {old_col} = student_id")
        op.drop_constraint(None, table, type_='foreignkey')
        op.drop_index(f'ix_{table}_student_id', table_name=table)
        op.create_foreign_key(old_fk_name, table, 'admission_visitors', [old_col], ['id'], ondelete='CASCADE')
        op.create_index(f'ix_{table}_{old_col}', table, [old_col], unique=True)
        op.drop_column(table, 'student_id')

    # consultancy_references  (student_id → admission_visitor_id)
    op.add_column('consultancy_references', sa.Column('admission_visitor_id', sa.UUID(), nullable=True))
    op.execute("UPDATE consultancy_references SET admission_visitor_id = student_id")
    op.drop_constraint(None, 'consultancy_references', type_='foreignkey')
    op.drop_index('ix_consultancy_references_student_id', table_name='consultancy_references')
    op.create_foreign_key('consultancy_references_admission_visitor_id_fkey', 'consultancy_references', 'admission_visitors', ['admission_visitor_id'], ['id'])
    op.create_unique_constraint('consultancy_references_admission_visitor_id_key', 'consultancy_references', ['admission_visitor_id'])
    op.drop_column('consultancy_references', 'student_id')

    # Drop new columns from admission_students
    op.drop_column('admission_students', 'check_out_remarks')
    op.drop_column('admission_students', 'check_out_time')
    op.drop_column('admission_students', 'check_in_time')
    op.drop_column('admission_students', 'visit_status')
    op.drop_column('admission_students', 'native_place')
    op.drop_column('admission_students', 'image_url')
    op.drop_column('admission_students', 'source')

    # Drop enum types
    sa.Enum(name='visitstatusenum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='sourceenum').drop(op.get_bind(), checkfirst=True)
