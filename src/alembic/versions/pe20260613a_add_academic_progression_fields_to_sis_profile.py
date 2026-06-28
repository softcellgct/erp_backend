"""add academic progression fields to sis_student_profiles

Adds the student's CURRENT academic position (year/semester/academic-year),
entry mode, batch, graduation year, academic status, promotion-eligibility
holds and lateral-entry diploma background to sis_student_profiles.

Idempotent: enum types are created via guarded DO-blocks and columns are added
only if missing, so the migration coexists safely with the app's startup
``Base.metadata.create_all`` (which may create the native enum types first).

Revision ID: pe20260613a
Revises: pe20260530c
Create Date: 2026-06-13 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'pe20260613a'
down_revision: Union[str, Sequence[str], None] = 'pe20260530c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reference the native enum types WITHOUT auto-creating them (create_type=False);
# the DO-blocks below own their creation.
ENTRY_MODE = postgresql.ENUM('NORMAL', 'LATERAL_ENTRY', 'TRANSFER', name='entry_mode_enum', create_type=False)
ACADEMIC_STATUS = postgresql.ENUM(
    'ACTIVE', 'PROMOTED', 'GRADUATED', 'DISCONTINUED', 'TRANSFERRED', 'ALUMNI',
    name='academic_status_enum', create_type=False,
)

_COLUMNS = [
    ('current_year_of_study', sa.Integer(), {}),
    ('current_semester', sa.Integer(), {}),
    ('current_academic_year_id', sa.UUID(), {}),
    ('entry_mode', ENTRY_MODE, {}),
    ('admission_batch', sa.String(length=20), {}),
    ('graduation_year', sa.Integer(), {}),
    ('academic_status', ACADEMIC_STATUS, {'nullable': False, 'server_default': 'ACTIVE'}),
    ('academic_hold', sa.Boolean(), {'nullable': False, 'server_default': sa.false()}),
    ('disciplinary_hold', sa.Boolean(), {'nullable': False, 'server_default': sa.false()}),
    ('hold_reason', sa.String(length=500), {}),
    ('diploma_institution', sa.String(length=255), {}),
    ('diploma_board', sa.String(length=255), {}),
    ('diploma_register_number', sa.String(length=100), {}),
    ('diploma_completion_year', sa.Integer(), {}),
    ('diploma_percentage', sa.String(length=20), {}),
    ('diploma_cgpa', sa.String(length=20), {}),
    ('diploma_branch', sa.String(length=255), {}),
    ('diploma_certificate_number', sa.String(length=100), {}),
]


def _create_enum(name: str, labels: list[str]) -> None:
    values = ", ".join(f"'{v}'" for v in labels)
    op.execute(
        f"DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN "
        f"CREATE TYPE {name} AS ENUM ({values}); "
        f"END IF; END $$;"
    )


def upgrade() -> None:
    _create_enum('entry_mode_enum', ['NORMAL', 'LATERAL_ENTRY', 'TRANSFER'])
    _create_enum('academic_status_enum', ['ACTIVE', 'PROMOTED', 'GRADUATED', 'DISCONTINUED', 'TRANSFERRED', 'ALUMNI'])

    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('sis_student_profiles')}
    for name, type_, kwargs in _COLUMNS:
        if name not in existing:
            op.add_column('sis_student_profiles', sa.Column(name, type_, nullable=kwargs.get('nullable', True), server_default=kwargs.get('server_default')))

    indexes = {ix['name'] for ix in sa.inspect(op.get_bind()).get_indexes('sis_student_profiles')}
    if 'ix_sis_student_profiles_current_academic_year_id' not in indexes:
        op.create_index(op.f('ix_sis_student_profiles_current_academic_year_id'), 'sis_student_profiles', ['current_academic_year_id'], unique=False)
    if 'ix_sis_student_profiles_admission_batch' not in indexes:
        op.create_index(op.f('ix_sis_student_profiles_admission_batch'), 'sis_student_profiles', ['admission_batch'], unique=False)

    fks = {fk['name'] for fk in sa.inspect(op.get_bind()).get_foreign_keys('sis_student_profiles')}
    if 'fk_sis_profile_current_academic_year' not in fks:
        op.create_foreign_key(
            'fk_sis_profile_current_academic_year',
            'sis_student_profiles', 'academic_years',
            ['current_academic_year_id'], ['id'],
        )


def downgrade() -> None:
    op.drop_constraint('fk_sis_profile_current_academic_year', 'sis_student_profiles', type_='foreignkey')
    op.drop_index(op.f('ix_sis_student_profiles_admission_batch'), table_name='sis_student_profiles')
    op.drop_index(op.f('ix_sis_student_profiles_current_academic_year_id'), table_name='sis_student_profiles')

    for name, _type, _kwargs in reversed(_COLUMNS):
        op.drop_column('sis_student_profiles', name)

    # academic_status_enum / entry_mode_enum are shared with
    # sis_student_academic_history (dropped first by pe20260613b's downgrade).
    op.execute("DROP TYPE IF EXISTS academic_status_enum;")
    op.execute("DROP TYPE IF EXISTS entry_mode_enum;")
