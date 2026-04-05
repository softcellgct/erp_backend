"""Split admission_students into gate + normalized detail tables

Revision ID: 20260404_adm_split
Revises: 20260324_multi_receipt_school
Create Date: 2026-04-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260404_adm_split"
down_revision: Union[str, Sequence[str], None] = "20260324_multi_receipt_school"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def _ensure_gate_table() -> None:
    if _has_table("admission_gate_entries"):
        return

    op.create_table(
        "admission_gate_entries",
        sa.Column("gate_pass_number", sa.String(length=50), nullable=False),
        sa.Column("reference_type", sa.String(length=100), nullable=True),
        sa.Column("student_name", sa.String(length=200), nullable=False),
        sa.Column("parent_or_guardian_name", sa.String(length=200), nullable=True),
        sa.Column("mobile_number", sa.String(length=15), nullable=True),
        sa.Column("aadhar_number", sa.String(length=12), nullable=True),
        sa.Column("native_place", sa.String(length=255), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("vehicle", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("vehicle_number", sa.String(length=20), nullable=True),
        sa.Column("institution_id", sa.UUID(), nullable=True),
        sa.Column(
            "visit_status",
            postgresql.ENUM(
                "PENDING",
                "CHECKED_IN",
                "CHECKED_OUT",
                "CANCELLED",
                name="visitstatusenum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'CHECKED_IN'"),
        ),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_remarks", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ENQUIRY",
                "ENQUIRED",
                "BOOKED",
                "APPLIED",
                "DOCUMENTS_PENDING",
                "DOCUMENTS_VERIFIED",
                "FEE_PENDING",
                "FEE_RECEIVED",
                "ADMISSION_GRANTED",
                "FORM_VERIFICATION_PENDING",
                "FORM_VERIFIED",
                "APPLICATION_RECEIVED",
                "PROVISIONALLY_ALLOTTED",
                "ENROLLED",
                "WAITLISTED",
                "REJECTED",
                "WITHDRAWN",
                "ON_HOLD",
                name="admissionstatusenum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'ENQUIRY'"),
        ),
        sa.Column("enquiry_number", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gate_pass_number"),
        sa.UniqueConstraint("enquiry_number"),
    )

    if not _has_index("admission_gate_entries", "ix_admission_gate_entries_gate_pass_number"):
        op.create_index("ix_admission_gate_entries_gate_pass_number", "admission_gate_entries", ["gate_pass_number"], unique=True)
    if not _has_index("admission_gate_entries", "ix_admission_gate_entries_student_name"):
        op.create_index("ix_admission_gate_entries_student_name", "admission_gate_entries", ["student_name"], unique=False)
    if not _has_index("admission_gate_entries", "ix_admission_gate_entries_aadhar_number"):
        op.create_index("ix_admission_gate_entries_aadhar_number", "admission_gate_entries", ["aadhar_number"], unique=False)
    if not _has_index("admission_gate_entries", "ix_admission_gate_entries_institution_id"):
        op.create_index("ix_admission_gate_entries_institution_id", "admission_gate_entries", ["institution_id"], unique=False)
    if not _has_index("admission_gate_entries", "ix_admission_gate_entries_enquiry_number"):
        op.create_index("ix_admission_gate_entries_enquiry_number", "admission_gate_entries", ["enquiry_number"], unique=True)


def _ensure_detail_tables() -> None:
    if not _has_table("admission_student_personal_details"):
        op.create_table(
            "admission_student_personal_details",
            sa.Column("admission_student_id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("father_name", sa.String(length=200), nullable=True),
            sa.Column(
                "gender",
                postgresql.ENUM("Male", "Female", "Other", name="genderenum", create_type=False),
                nullable=True,
            ),
            sa.Column("date_of_birth", sa.Date(), nullable=True),
            sa.Column("student_mobile", sa.String(length=15), nullable=True),
            sa.Column("parent_mobile", sa.String(length=15), nullable=True),
            sa.Column("aadhaar_number", sa.String(length=12), nullable=True),
            sa.Column("religion", sa.String(length=50), nullable=True),
            sa.Column("community", sa.String(length=50), nullable=True),
            sa.Column("caste", sa.String(length=50), nullable=True),
            sa.Column("parent_income", sa.Numeric(12, 2), nullable=True),
            sa.Column("door_no", sa.String(length=50), nullable=True),
            sa.Column("street_name", sa.String(length=200), nullable=True),
            sa.Column("village_name", sa.String(length=100), nullable=True),
            sa.Column("taluk", sa.String(length=100), nullable=True),
            sa.Column("district", sa.String(length=100), nullable=True),
            sa.Column("state", sa.String(length=100), nullable=True),
            sa.Column("pincode", sa.String(length=10), nullable=True),
            sa.Column("parent_address", sa.Text(), nullable=True),
            sa.Column("permanent_address", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.UUID(), nullable=True),
            sa.Column("updated_by", sa.UUID(), nullable=True),
            sa.Column("deleted_by", sa.UUID(), nullable=True),
            sa.ForeignKeyConstraint(["admission_student_id"], ["admission_students.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("admission_student_id"),
        )
        op.create_index("ix_admission_student_personal_details_admission_student_id", "admission_student_personal_details", ["admission_student_id"], unique=True)
        op.create_index("ix_admission_student_personal_details_aadhaar_number", "admission_student_personal_details", ["aadhaar_number"], unique=False)

    if not _has_table("admission_student_program_details"):
        op.create_table(
            "admission_student_program_details",
            sa.Column("admission_student_id", sa.UUID(), nullable=False),
            sa.Column("campus", sa.String(length=200), nullable=True),
            sa.Column("institution_id", sa.UUID(), nullable=True),
            sa.Column("department_id", sa.UUID(), nullable=True),
            sa.Column("course_id", sa.UUID(), nullable=True),
            sa.Column("academic_year_id", sa.UUID(), nullable=True),
            sa.Column("year", sa.String(length=20), nullable=True),
            sa.Column("branch", sa.String(length=200), nullable=True),
            sa.Column(
                "previous_academic_level",
                postgresql.ENUM("10th", "12th", "Diploma", "Degree", name="previousacademiclevelenum", create_type=False),
                nullable=True,
            ),
            sa.Column("is_lateral_entry", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("admission_quota_id", sa.UUID(), nullable=True),
            sa.Column(
                "category",
                postgresql.ENUM("General", "OBC", "SC", "ST", "MBC", "DNC", "Others", name="categoryenum", create_type=False),
                nullable=True,
            ),
            sa.Column("quota_type", sa.String(length=50), nullable=True),
            sa.Column("special_quota", sa.String(length=100), nullable=True),
            sa.Column("scholarships", sa.String(length=200), nullable=True),
            sa.Column("boarding_place", sa.String(length=200), nullable=True),
            sa.Column("admission_type_id", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.UUID(), nullable=True),
            sa.Column("updated_by", sa.UUID(), nullable=True),
            sa.Column("deleted_by", sa.UUID(), nullable=True),
            sa.ForeignKeyConstraint(["admission_student_id"], ["admission_students.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
            sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
            sa.ForeignKeyConstraint(["admission_quota_id"], ["seat_quotas.id"]),
            sa.ForeignKeyConstraint(["admission_type_id"], ["admission_types.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("admission_student_id"),
        )
        op.create_index("ix_admission_student_program_details_admission_student_id", "admission_student_program_details", ["admission_student_id"], unique=True)
        op.create_index("ix_admission_student_program_details_institution_id", "admission_student_program_details", ["institution_id"], unique=False)
        op.create_index("ix_admission_student_program_details_department_id", "admission_student_program_details", ["department_id"], unique=False)
        op.create_index("ix_admission_student_program_details_course_id", "admission_student_program_details", ["course_id"], unique=False)
        op.create_index("ix_admission_student_program_details_academic_year_id", "admission_student_program_details", ["academic_year_id"], unique=False)

    if not _has_table("admission_student_previous_academic_details"):
        op.create_table(
            "admission_student_previous_academic_details",
            sa.Column("admission_student_id", sa.UUID(), nullable=False),
            sa.Column("sslc", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("hsc", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("diploma", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("degree", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.UUID(), nullable=True),
            sa.Column("updated_by", sa.UUID(), nullable=True),
            sa.Column("deleted_by", sa.UUID(), nullable=True),
            sa.ForeignKeyConstraint(["admission_student_id"], ["admission_students.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], deferrable=True, initially="DEFERRED", use_alter=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("admission_student_id"),
        )
        op.create_index(
            "ix_admission_student_previous_academic_details_admission_student_id",
            "admission_student_previous_academic_details",
            ["admission_student_id"],
            unique=True,
        )


def _ensure_gate_links_on_admissions() -> None:
    if not _has_column("admission_students", "gate_entry_id"):
        op.add_column("admission_students", sa.Column("gate_entry_id", sa.UUID(), nullable=True))
    if not _has_index("admission_students", "ix_admission_students_gate_entry_id"):
        op.create_index("ix_admission_students_gate_entry_id", "admission_students", ["gate_entry_id"], unique=True)

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("admission_students")}
    if "fk_admission_students_gate_entry_id" not in fk_names:
        op.create_foreign_key(
            "fk_admission_students_gate_entry_id",
            "admission_students",
            "admission_gate_entries",
            ["gate_entry_id"],
            ["id"],
            ondelete="SET NULL",
        )


def _ensure_reference_gate_columns() -> None:
    tables = [
        "consultancy_references",
        "staff_references",
        "student_references",
        "other_references",
    ]

    for table_name in tables:
        if not _has_column(table_name, "gate_entry_id"):
            op.add_column(table_name, sa.Column("gate_entry_id", sa.UUID(), nullable=True))

        index_name = f"ix_{table_name}_gate_entry_id"
        if not _has_index(table_name, index_name):
            op.create_index(index_name, table_name, ["gate_entry_id"], unique=True)

        bind = op.get_bind()
        inspector = sa.inspect(bind)
        fk_names = {fk["name"] for fk in inspector.get_foreign_keys(table_name)}
        fk_name = f"fk_{table_name}_gate_entry_id"
        if fk_name not in fk_names:
            op.create_foreign_key(
                fk_name,
                table_name,
                "admission_gate_entries",
                ["gate_entry_id"],
                ["id"],
                ondelete="CASCADE",
            )

        if _has_column(table_name, "student_id"):
            op.alter_column(table_name, "student_id", nullable=True)


def _backfill_gate_entries() -> None:
    op.execute(
        """
        INSERT INTO admission_gate_entries (
            id, created_at, updated_at, deleted_at,
            created_by, updated_by, deleted_by,
            gate_pass_number, reference_type,
            student_name, parent_or_guardian_name, mobile_number, aadhar_number,
            native_place, image_url,
            vehicle, vehicle_number,
            institution_id,
            visit_status, check_in_time, check_out_time, check_out_remarks,
            status, enquiry_number
        )
        SELECT
            s.id,
            s.created_at,
            s.updated_at,
            s.deleted_at,
            s.created_by,
            s.updated_by,
            s.deleted_by,
            COALESCE(NULLIF(s.gate_pass_number, ''), NULLIF(s.enquiry_number, ''), LEFT('LEGACY-' || s.id::text, 50)),
            s.reference_type,
            COALESCE(NULLIF(s.name, ''), 'Unknown'),
            s.father_name,
            s.student_mobile,
            s.aadhaar_number,
            s.native_place,
            s.image_url,
            COALESCE(s.has_vehicle, false),
            s.vehicle_number,
            s.institution_id,
            COALESCE(s.visit_status::text, 'CHECKED_IN')::visitstatusenum,
            COALESCE(s.check_in_time, s.created_at, now()),
            s.check_out_time,
            s.check_out_remarks,
            COALESCE(s.status::text, 'ENQUIRY')::admissionstatusenum,
            s.enquiry_number
        FROM admission_students s
        WHERE (s.gate_pass_number IS NOT NULL OR s.source = 'GATE_ENQUIRY')
          AND NOT EXISTS (
            SELECT 1 FROM admission_gate_entries g WHERE g.id = s.id
          );
        """
    )

    op.execute(
        """
        UPDATE admission_students s
        SET gate_entry_id = s.id
        WHERE (s.gate_pass_number IS NOT NULL OR s.source = 'GATE_ENQUIRY')
          AND s.gate_entry_id IS NULL
          AND EXISTS (SELECT 1 FROM admission_gate_entries g WHERE g.id = s.id);
        """
    )


def _backfill_detail_tables() -> None:
    op.execute(
        """
        INSERT INTO admission_student_personal_details (
            id, created_at, updated_at, deleted_at,
            created_by, updated_by, deleted_by,
            admission_student_id,
            name, father_name, gender, date_of_birth,
            student_mobile, parent_mobile, aadhaar_number,
            religion, community, caste, parent_income,
            door_no, street_name, village_name, taluk,
            district, state, pincode, parent_address, permanent_address
        )
        SELECT
            s.id,
            s.created_at,
            s.updated_at,
            s.deleted_at,
            s.created_by,
            s.updated_by,
            s.deleted_by,
            s.id,
            COALESCE(NULLIF(s.name, ''), 'Unknown'),
            s.father_name,
            s.gender,
            s.date_of_birth,
            s.student_mobile,
            s.parent_mobile,
            s.aadhaar_number,
            s.religion,
            s.community,
            s.caste,
            s.parent_income,
            s.door_no,
            s.street_name,
            s.village_name,
            s.taluk,
            s.district,
            s.state,
            s.pincode,
            s.parent_address,
            s.permanent_address
        FROM admission_students s
        WHERE NOT EXISTS (
            SELECT 1 FROM admission_student_personal_details p WHERE p.admission_student_id = s.id
        );
        """
    )

    op.execute(
        """
        INSERT INTO admission_student_program_details (
            id, created_at, updated_at, deleted_at,
            created_by, updated_by, deleted_by,
            admission_student_id,
            campus, institution_id, department_id, course_id, academic_year_id,
            year, branch, previous_academic_level, is_lateral_entry,
            admission_quota_id, category, quota_type, special_quota,
            scholarships, boarding_place, admission_type_id
        )
        SELECT
            s.id,
            s.created_at,
            s.updated_at,
            s.deleted_at,
            s.created_by,
            s.updated_by,
            s.deleted_by,
            s.id,
            s.campus,
            s.institution_id,
            s.department_id,
            s.course_id,
            s.academic_year_id,
            s.year,
            s.branch,
            s.previous_academic_level,
            COALESCE(s.is_lateral_entry, false),
            s.admission_quota_id,
            s.category,
            s.quota_type,
            s.special_quota,
            s.scholarships,
            s.boarding_place,
            s.admission_type_id
        FROM admission_students s
        WHERE NOT EXISTS (
            SELECT 1 FROM admission_student_program_details p WHERE p.admission_student_id = s.id
        );
        """
    )

    op.execute(
        """
        INSERT INTO admission_student_previous_academic_details (
            id, created_at, updated_at, deleted_at,
            created_by, updated_by, deleted_by,
            admission_student_id,
            sslc, hsc, diploma, degree
        )
        SELECT
            s.id,
            s.created_at,
            s.updated_at,
            s.deleted_at,
            s.created_by,
            s.updated_by,
            s.deleted_by,
            s.id,
            CASE WHEN sd.student_id IS NOT NULL THEN
                jsonb_build_object(
                    'register_number', sd.register_number,
                    'school_name', sd.school_name,
                    'school_block', sd.school_block,
                    'school_district', sd.school_district,
                    'board', sd.board,
                    'year_of_passing', sd.year_of_passing,
                    'marks', sd.marks,
                    'total_marks', sd.total_marks,
                    'percentage', sd.percentage
                )
            ELSE NULL END,
            CASE WHEN hd.student_id IS NOT NULL THEN
                jsonb_build_object(
                    'register_number', hd.register_number,
                    'school_name', hd.school_name,
                    'school_block', hd.school_block,
                    'school_district', hd.school_district,
                    'board', hd.board,
                    'year_of_passing', hd.year_of_passing,
                    'total_marks', hd.total_marks,
                    'obtained_marks', hd.obtained_marks,
                    'percentage', hd.percentage,
                    'maths_mark', hd.maths_mark,
                    'physics_mark', hd.physics_mark,
                    'chemistry_mark', hd.chemistry_mark,
                    'pcm_percentage', hd.pcm_percentage,
                    'cutoff_mark', hd.cutoff_mark,
                    'subject_marks', (
                        SELECT COALESCE(jsonb_agg(jsonb_build_object(
                            'subject_name', hm.subject_name,
                            'subject_variant', hm.subject_variant,
                            'total_marks', hm.total_marks,
                            'obtained_marks', hm.obtained_marks
                        )), '[]'::jsonb)
                        FROM hsc_subject_marks hm
                        WHERE hm.hsc_details_id = hd.id
                    )
                )
            ELSE NULL END,
            CASE WHEN dd.student_id IS NOT NULL THEN
                jsonb_build_object(
                    'college_name', dd.college_name,
                    'department', dd.department,
                    'register_number', dd.register_number,
                    'year_of_passing', dd.year_of_passing,
                    'percentage', dd.percentage,
                    'cgpa', dd.cgpa
                )
            ELSE NULL END,
            CASE WHEN pd.student_id IS NOT NULL THEN
                jsonb_build_object(
                    'degree_name', pd.degree_name,
                    'department', pd.department,
                    'college_name', pd.college_name,
                    'register_number', pd.register_number,
                    'year_of_passing', pd.year_of_passing,
                    'percentage', pd.percentage,
                    'cgpa', pd.cgpa
                )
            ELSE NULL END
        FROM admission_students s
        LEFT JOIN sslc_details sd ON sd.student_id = s.id
        LEFT JOIN hsc_details hd ON hd.student_id = s.id
        LEFT JOIN diploma_details dd ON dd.student_id = s.id
        LEFT JOIN pg_details pd ON pd.student_id = s.id
        WHERE NOT EXISTS (
            SELECT 1 FROM admission_student_previous_academic_details pa WHERE pa.admission_student_id = s.id
        );
        """
    )


def _backfill_references() -> None:
    tables = [
        "consultancy_references",
        "staff_references",
        "student_references",
        "other_references",
    ]

    for table_name in tables:
        op.execute(
            f"""
            UPDATE {table_name} r
            SET gate_entry_id = s.gate_entry_id
            FROM admission_students s
            WHERE r.student_id = s.id
              AND r.gate_entry_id IS NULL
              AND s.gate_entry_id IS NOT NULL;
            """
        )

        op.execute(
            f"""
            UPDATE {table_name} r
            SET student_id = s.id
            FROM admission_students s
            WHERE r.gate_entry_id = s.gate_entry_id
              AND r.student_id IS NULL;
            """
        )


def upgrade() -> None:
    _ensure_gate_table()
    _ensure_gate_links_on_admissions()
    _ensure_detail_tables()
    _ensure_reference_gate_columns()

    _backfill_gate_entries()
    _backfill_detail_tables()
    _backfill_references()


def downgrade() -> None:
    # Best effort rollback: remove new linkage columns and tables.
    for table_name in [
        "consultancy_references",
        "staff_references",
        "student_references",
        "other_references",
    ]:
        if _has_column(table_name, "gate_entry_id"):
            fk_name = f"fk_{table_name}_gate_entry_id"
            bind = op.get_bind()
            inspector = sa.inspect(bind)
            fk_names = {fk["name"] for fk in inspector.get_foreign_keys(table_name)}
            if fk_name in fk_names:
                op.drop_constraint(fk_name, table_name, type_="foreignkey")

            idx_name = f"ix_{table_name}_gate_entry_id"
            if _has_index(table_name, idx_name):
                op.drop_index(idx_name, table_name=table_name)

            op.drop_column(table_name, "gate_entry_id")

    if _has_table("admission_student_previous_academic_details"):
        op.drop_table("admission_student_previous_academic_details")
    if _has_table("admission_student_program_details"):
        op.drop_table("admission_student_program_details")
    if _has_table("admission_student_personal_details"):
        op.drop_table("admission_student_personal_details")

    if _has_column("admission_students", "gate_entry_id"):
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        fk_names = {fk["name"] for fk in inspector.get_foreign_keys("admission_students")}
        if "fk_admission_students_gate_entry_id" in fk_names:
            op.drop_constraint("fk_admission_students_gate_entry_id", "admission_students", type_="foreignkey")
        if _has_index("admission_students", "ix_admission_students_gate_entry_id"):
            op.drop_index("ix_admission_students_gate_entry_id", table_name="admission_students")
        op.drop_column("admission_students", "gate_entry_id")

    if _has_table("admission_gate_entries"):
        op.drop_table("admission_gate_entries")
