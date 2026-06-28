"""create sis_student_academic_history table

Immutable audit trail of every academic transition (admission, promotion,
lateral entry, graduation). Reuses entry_mode_enum / academic_status_enum from
pe20260613a and creates promotion_type_enum.

Idempotent: the enum type is created via a guarded DO-block and the table only
if it does not already exist, so the migration coexists with the app's startup
``Base.metadata.create_all``.

Revision ID: pe20260613b
Revises: pe20260613a
Create Date: 2026-06-13 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'pe20260613b'
down_revision: Union[str, Sequence[str], None] = 'pe20260613a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All three enum types already exist (created in pe20260613a / by this file's
# DO-block) — reference them without auto-creation.
PROMOTION_TYPE = postgresql.ENUM('ADMISSION', 'PROMOTION', 'LATERAL_ENTRY', 'GRADUATION', name='promotion_type_enum', create_type=False)
ENTRY_MODE = postgresql.ENUM('NORMAL', 'LATERAL_ENTRY', 'TRANSFER', name='entry_mode_enum', create_type=False)
ACADEMIC_STATUS = postgresql.ENUM('ACTIVE', 'PROMOTED', 'GRADUATED', 'DISCONTINUED', 'TRANSFERRED', 'ALUMNI', name='academic_status_enum', create_type=False)

_INDEXES = [
    'deleted_at', 'student_id', 'institution_id', 'department_id',
    'course_id', 'academic_year_id', 'roll_number', 'register_number',
]


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'promotion_type_enum') THEN "
        "CREATE TYPE promotion_type_enum AS ENUM ('ADMISSION', 'PROMOTION', 'LATERAL_ENTRY', 'GRADUATION'); "
        "END IF; END $$;"
    )

    if sa.inspect(op.get_bind()).has_table('sis_student_academic_history'):
        return

    op.create_table(
        'sis_student_academic_history',
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('institution_id', sa.UUID(), nullable=True),
        sa.Column('department_id', sa.UUID(), nullable=True),
        sa.Column('course_id', sa.UUID(), nullable=True),
        sa.Column('academic_year_id', sa.UUID(), nullable=True),
        sa.Column('semester', sa.Integer(), nullable=True),
        sa.Column('year_of_study', sa.Integer(), nullable=True),
        sa.Column('section', sa.String(length=50), nullable=True),
        sa.Column('roll_number', sa.String(length=50), nullable=True),
        sa.Column('register_number', sa.String(length=100), nullable=True),
        sa.Column('promotion_type', PROMOTION_TYPE, nullable=False),
        sa.Column('entry_mode', ENTRY_MODE, nullable=True),
        sa.Column('status', ACADEMIC_STATUS, nullable=True),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['admission_students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_sis_acad_hist_created_by_users', initially='DEFERRED', deferrable=True, use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_sis_acad_hist_updated_by_users', initially='DEFERRED', deferrable=True, use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_sis_acad_hist_deleted_by_users', initially='DEFERRED', deferrable=True, use_alter=True),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in _INDEXES:
        op.create_index(op.f(f'ix_sis_student_academic_history_{col}'), 'sis_student_academic_history', [col], unique=False)


def downgrade() -> None:
    for col in reversed(_INDEXES):
        op.drop_index(op.f(f'ix_sis_student_academic_history_{col}'), table_name='sis_student_academic_history')
    op.drop_table('sis_student_academic_history')
    op.execute("DROP TYPE IF EXISTS promotion_type_enum;")
