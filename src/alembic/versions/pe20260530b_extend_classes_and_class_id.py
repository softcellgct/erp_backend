"""extend classes for sections + add class_id to admission_students

Revision ID: pe20260530b
Revises: pe20260530a
Create Date: 2026-05-30 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'pe20260530b'
down_revision: Union[str, Sequence[str], None] = 'pe20260530a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend classes into (course + academic_year + section) groups ──
    op.add_column('classes', sa.Column('academic_year_id', sa.UUID(), nullable=True))
    op.add_column('classes', sa.Column('institution_id', sa.UUID(), nullable=True))
    op.add_column('classes', sa.Column('section_name', sa.String(length=50), nullable=True))
    op.add_column('classes', sa.Column('capacity', sa.Integer(), nullable=True))

    op.create_index(op.f('ix_classes_academic_year_id'), 'classes', ['academic_year_id'], unique=False)
    op.create_index(op.f('ix_classes_institution_id'), 'classes', ['institution_id'], unique=False)
    op.create_foreign_key(
        'fk_classes_academic_year', 'classes', 'academic_years', ['academic_year_id'], ['id']
    )
    op.create_foreign_key(
        'fk_classes_institution', 'classes', 'institutions', ['institution_id'], ['id']
    )
    op.create_unique_constraint(
        'uq_class_course_year_section', 'classes', ['course_id', 'academic_year_id', 'section_name']
    )

    # ── Student → class assignment ──
    op.add_column('admission_students', sa.Column('class_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_admission_students_class_id'), 'admission_students', ['class_id'], unique=False)
    op.create_foreign_key(
        'fk_admission_students_class', 'admission_students', 'classes', ['class_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_admission_students_class', 'admission_students', type_='foreignkey')
    op.drop_index(op.f('ix_admission_students_class_id'), table_name='admission_students')
    op.drop_column('admission_students', 'class_id')

    op.drop_constraint('uq_class_course_year_section', 'classes', type_='unique')
    op.drop_constraint('fk_classes_institution', 'classes', type_='foreignkey')
    op.drop_constraint('fk_classes_academic_year', 'classes', type_='foreignkey')
    op.drop_index(op.f('ix_classes_institution_id'), table_name='classes')
    op.drop_index(op.f('ix_classes_academic_year_id'), table_name='classes')
    op.drop_column('classes', 'capacity')
    op.drop_column('classes', 'section_name')
    op.drop_column('classes', 'institution_id')
    op.drop_column('classes', 'academic_year_id')
