"""Add scholarship, refund, semester-wise fees support

Revision ID: semester_scholarship_refund_001
Revises: admission_redesign_001
Create Date: 2026-03-04

Changes:
1. Create student_scholarships table
2. Create refunds table
3. Add fg_amount, sc_st_amount, semesters_per_year, fg_amount_by_semester to fee_structures
4. Make fee_sub_head_id nullable on fee_structure_items
5. Add amount_by_semester to fee_structure_items
6. Add semester, year columns to demand_items
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision = 'semester_scholarship_refund_001'
down_revision = 'admission_redesign_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── 1. Create student_scholarships table (guard if exists) ──
    if not inspector.has_table('student_scholarships'):
        op.create_table(
            'student_scholarships',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('admission_students.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('fee_structure_id', UUID(as_uuid=True), sa.ForeignKey('fee_structures.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('academic_year_id', UUID(as_uuid=True), sa.ForeignKey('academic_years.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('scholarship_type', sa.String(20), nullable=False),
            sa.Column('certificate_status', sa.String(20), nullable=False, server_default='NOT_SUBMITTED'),
            sa.Column('certificate_file', sa.String(500), nullable=True),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('amount_received', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('amount_received_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('receipt_id', UUID(as_uuid=True), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('meta', JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_by', UUID(as_uuid=True), nullable=True),
            sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
            sa.Column('deleted_by', UUID(as_uuid=True), nullable=True),
        )

    # ── 2. Create refunds table (guard if exists) ──
    if not inspector.has_table('refunds'):
        op.create_table(
            'refunds',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('admission_students.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('original_payment_id', UUID(as_uuid=True), sa.ForeignKey('payments.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('original_invoice_id', UUID(as_uuid=True), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('original_amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('cancellation_fee', sa.Numeric(12, 2), nullable=False),
            sa.Column('refund_amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('refund_method', sa.String(30), nullable=True),
            sa.Column('refund_reference', sa.String(200), nullable=True),
            sa.Column('cancellation_receipt_number', sa.String(100), unique=True, nullable=True),
            sa.Column('refund_receipt_number', sa.String(100), unique=True, nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='INITIATED'),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('initiated_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('approved_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('meta', JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_by', UUID(as_uuid=True), nullable=True),
            sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
            sa.Column('deleted_by', UUID(as_uuid=True), nullable=True),
            sa.CheckConstraint('original_amount >= 0', name='ck_refund_original_amount'),
            sa.CheckConstraint('cancellation_fee >= 0', name='ck_refund_cancellation_fee'),
            sa.CheckConstraint('refund_amount >= 0', name='ck_refund_amount'),
        )

    # ── 3. ALTER fee_structures: add new columns ──
    # ── 3. ALTER fee_structures: add new columns if absent ──
    fee_structure_cols = {c['name'] for c in inspector.get_columns('fee_structures')} if inspector.has_table('fee_structures') else set()
    if 'semesters_per_year' not in fee_structure_cols:
        op.add_column('fee_structures', sa.Column('semesters_per_year', sa.Integer(), nullable=False, server_default='2'))
    if 'fg_amount' not in fee_structure_cols:
        op.add_column('fee_structures', sa.Column('fg_amount', sa.Numeric(12, 2), nullable=True))
    if 'sc_st_amount' not in fee_structure_cols:
        op.add_column('fee_structures', sa.Column('sc_st_amount', sa.Numeric(12, 2), nullable=True))
    if 'fg_amount_by_semester' not in fee_structure_cols:
        op.add_column('fee_structures', sa.Column('fg_amount_by_semester', JSON(), nullable=True))

    # ── 4. ALTER fee_structure_items: make fee_sub_head_id nullable, add amount_by_semester ──
    # ── 4. ALTER fee_structure_items: make fee_sub_head_id nullable, add amount_by_semester if absent ──
    if inspector.has_table('fee_structure_items'):
        fsi_cols = {c['name'] for c in inspector.get_columns('fee_structure_items')}
        if 'fee_sub_head_id' in fsi_cols:
            try:
                op.alter_column('fee_structure_items', 'fee_sub_head_id', existing_type=UUID(as_uuid=True), nullable=True)
            except Exception:
                # best-effort: ignore if altering fails (e.g., already nullable)
                pass
        if 'amount_by_semester' not in fsi_cols:
            op.add_column('fee_structure_items', sa.Column('amount_by_semester', JSON(), nullable=True))

    # ── 5. ALTER demand_items: add semester and year ──
    # ── 5. ALTER demand_items: add semester and year if absent ──
    if inspector.has_table('demand_items'):
        di_cols = {c['name'] for c in inspector.get_columns('demand_items')}
        if 'semester' not in di_cols:
            op.add_column('demand_items', sa.Column('semester', sa.Integer(), nullable=True))
        if 'year' not in di_cols:
            op.add_column('demand_items', sa.Column('year', sa.Integer(), nullable=True))


def downgrade() -> None:
    # ── Reverse demand_items changes ──
    op.drop_column('demand_items', 'year')
    op.drop_column('demand_items', 'semester')

    # ── Reverse fee_structure_items changes ──
    op.drop_column('fee_structure_items', 'amount_by_semester')
    op.alter_column('fee_structure_items', 'fee_sub_head_id', existing_type=UUID(as_uuid=True), nullable=False)

    # ── Reverse fee_structures changes ──
    op.drop_column('fee_structures', 'fg_amount_by_semester')
    op.drop_column('fee_structures', 'sc_st_amount')
    op.drop_column('fee_structures', 'fg_amount')
    op.drop_column('fee_structures', 'semesters_per_year')

    # ── Drop new tables ──
    op.drop_table('refunds')
    op.drop_table('student_scholarships')
