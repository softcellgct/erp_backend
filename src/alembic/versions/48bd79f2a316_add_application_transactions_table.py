"""Add application_transactions table

Revision ID: 48bd79f2a316
Revises: 4a5576c257cc
Create Date: 2026-01-15 10:28:55.410471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '48bd79f2a316'
down_revision: Union[str, Sequence[str], None] = '4a5576c257cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('application_transactions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('student_name', sa.String(length=255), nullable=False),
    sa.Column('student_mobile', sa.String(length=20), nullable=False),
    sa.Column('academic_year_id', sa.UUID(), nullable=False),
    sa.Column('department_id', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Float(precision=2), nullable=False),
    sa.Column('payment_mode', sa.String(length=50), nullable=False),
    sa.Column('transaction_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('cash_counter_id', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('receipt_number', sa.String(length=100), nullable=False),
    sa.Column('payment_status', postgresql.ENUM('PENDING', 'PAID', 'PARTIAL', 'OVERDUE', 'CANCELLED', name='paymentstatusenum', create_type=False), nullable=False),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_by', sa.UUID(), nullable=True),
    sa.Column('deleted_by', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['cash_counter_id'], ['cash_counters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_application_transactions_academic_year_id'), 'application_transactions', ['academic_year_id'], unique=False)
    op.create_index(op.f('ix_application_transactions_department_id'), 'application_transactions', ['department_id'], unique=False)
    op.create_index(op.f('ix_application_transactions_receipt_number'), 'application_transactions', ['receipt_number'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_application_transactions_receipt_number'), table_name='application_transactions')
    op.drop_index(op.f('ix_application_transactions_department_id'), table_name='application_transactions')
    op.drop_index(op.f('ix_application_transactions_academic_year_id'), table_name='application_transactions')
    op.drop_table('application_transactions')
