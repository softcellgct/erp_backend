"""Admission form redesign: lateral entry, school master, board, subject marks

Revision ID: admission_redesign_001
Revises: 
Create Date: 2026-02-27

Changes:
1. Add is_lateral_entry to admission_students
2. Add board, school_block to sslc_details
3. Add board, school_block to hsc_details
4. Create hsc_subject_marks table
5. Create school_master table
6. Create school_list_uploads table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'admission_redesign_001'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add is_lateral_entry to admission_students
    op.add_column('admission_students', sa.Column('is_lateral_entry', sa.Boolean(), nullable=False, server_default='false'))

    # 2. Add board and school_block to sslc_details
    op.add_column('sslc_details', sa.Column('board', sa.String(100), nullable=True))
    op.add_column('sslc_details', sa.Column('school_block', sa.String(200), nullable=True))

    # 3. Add board and school_block to hsc_details
    op.add_column('hsc_details', sa.Column('board', sa.String(100), nullable=True))
    op.add_column('hsc_details', sa.Column('school_block', sa.String(200), nullable=True))

    # 4. Create hsc_subject_marks table
    op.create_table(
        'hsc_subject_marks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('hsc_details_id', UUID(as_uuid=True), sa.ForeignKey('hsc_details.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('subject_name', sa.String(100), nullable=False),
        sa.Column('subject_variant', sa.String(100), nullable=True),
        sa.Column('total_marks', sa.Float(), nullable=False),
        sa.Column('obtained_marks', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', UUID(as_uuid=True), nullable=True),
    )

    # 5. Create school_master table
    op.create_table(
        'school_master',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(500), nullable=False, index=True),
        sa.Column('block', sa.String(200), nullable=True, index=True),
        sa.Column('district', sa.String(200), nullable=True, index=True),
        sa.Column('state', sa.String(100), nullable=True, server_default='Tamil Nadu'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', UUID(as_uuid=True), nullable=True),
    )

    # 6. Create school_list_uploads table
    op.create_table(
        'school_list_uploads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('file_name', sa.String(500), nullable=False),
        sa.Column('file_url', sa.String(1000), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('upload_status', sa.String(50), nullable=False, server_default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('school_list_uploads')
    op.drop_table('school_master')
    op.drop_table('hsc_subject_marks')
    op.drop_column('hsc_details', 'school_block')
    op.drop_column('hsc_details', 'board')
    op.drop_column('sslc_details', 'school_block')
    op.drop_column('sslc_details', 'board')
    op.drop_column('admission_students', 'is_lateral_entry')
