"""Add scholarship configuration and staff referral concession tables

Revision ID: scholarship_config_001
Revises: 2ad28a0a3bf9
Create Date: 2026-04-10

Changes:
1. Create scholarship_configurations table
2. Create staff_referral_concessions table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision = 'scholarship_config_001'
down_revision = '2ad28a0a3bf9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── 1. Create scholarship_configurations table (guard if exists) ──
    if not inspector.has_table('scholarship_configurations'):
        op.create_table(
            'scholarship_configurations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('scholarship_type', sa.String(50), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=True),
            sa.Column('percentage', sa.Numeric(5, 2), nullable=True),
            sa.Column('fee_head_id', UUID(as_uuid=True), sa.ForeignKey('fee_heads.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('description', sa.String(500), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('reduce_from_tuition', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('meta', JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        op.create_index('ix_scholarship_configurations_institution_id', 'scholarship_configurations', ['institution_id'])
        op.create_index('ix_scholarship_configurations_fee_head_id', 'scholarship_configurations', ['fee_head_id'])

    # ── 2. Create staff_referral_concessions table (guard if exists) ──
    if not inspector.has_table('staff_referral_concessions'):
        op.create_table(
            'staff_referral_concessions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('staff_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('admission_students.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('concession_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('concession_percentage', sa.Numeric(5, 2), nullable=True),
            sa.Column('fee_head_id', UUID(as_uuid=True), sa.ForeignKey('fee_heads.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('is_applied', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('notes', sa.String(500), nullable=True),
            sa.Column('meta', JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        op.create_index('ix_staff_referral_concessions_staff_id', 'staff_referral_concessions', ['staff_id'])
        op.create_index('ix_staff_referral_concessions_student_id', 'staff_referral_concessions', ['student_id'])
        op.create_index('ix_staff_referral_concessions_institution_id', 'staff_referral_concessions', ['institution_id'])
        op.create_index('ix_staff_referral_concessions_fee_head_id', 'staff_referral_concessions', ['fee_head_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop tables in reverse order
    if inspector.has_table('staff_referral_concessions'):
        op.drop_table('staff_referral_concessions')
    
    if inspector.has_table('scholarship_configurations'):
        op.drop_table('scholarship_configurations')
