"""update_demand_batch_schema

Revision ID: 0c7084aeb2a0
Revises: 95201cfe47d3
Create Date: 2026-01-15 09:09:36.676248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0c7084aeb2a0'
down_revision: Union[str, Sequence[str], None] = '95201cfe47d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # demand_batches updates
    op.add_column('demand_batches', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('demand_batches', sa.Column('created_by', sa.UUID(), nullable=True))
    op.add_column('demand_batches', sa.Column('updated_by', sa.UUID(), nullable=True))
    op.add_column('demand_batches', sa.Column('deleted_by', sa.UUID(), nullable=True))
    op.alter_column('demand_batches', 'generated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=sa.DateTime(),
               existing_nullable=True)
    op.create_index(op.f('ix_demand_batches_admission_year_id'), 'demand_batches', ['admission_year_id'], unique=False)
    op.create_index(op.f('ix_demand_batches_fee_structure_id'), 'demand_batches', ['fee_structure_id'], unique=False)
    op.create_index(op.f('ix_demand_batches_institution_id'), 'demand_batches', ['institution_id'], unique=False)
    op.create_foreign_key(None, 'demand_batches', 'fee_structures', ['fee_structure_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'demand_batches', 'users', ['updated_by'], ['id'], initially='DEFERRED', deferrable=True, use_alter=True)
    op.create_foreign_key(None, 'demand_batches', 'users', ['deleted_by'], ['id'], initially='DEFERRED', deferrable=True, use_alter=True)
    op.create_foreign_key(None, 'demand_batches', 'academic_years', ['admission_year_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'demand_batches', 'institutions', ['institution_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'demand_batches', 'users', ['created_by'], ['id'], initially='DEFERRED', deferrable=True, use_alter=True)

    # demand_items updates
    op.add_column('demand_items', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('demand_items', sa.Column('created_by', sa.UUID(), nullable=True))
    op.add_column('demand_items', sa.Column('updated_by', sa.UUID(), nullable=True))
    op.add_column('demand_items', sa.Column('deleted_by', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_demand_items_batch_id'), 'demand_items', ['batch_id'], unique=False)
    op.create_index(op.f('ix_demand_items_fee_structure_id'), 'demand_items', ['fee_structure_id'], unique=False)
    op.create_index(op.f('ix_demand_items_fee_structure_item_id'), 'demand_items', ['fee_structure_item_id'], unique=False)
    op.create_index(op.f('ix_demand_items_invoice_id'), 'demand_items', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_demand_items_student_id'), 'demand_items', ['student_id'], unique=False)
    op.create_foreign_key(None, 'demand_items', 'users', ['deleted_by'], ['id'], initially='DEFERRED', deferrable=True, use_alter=True)
    op.create_foreign_key(None, 'demand_items', 'fee_structures', ['fee_structure_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'demand_items', 'fee_structure_items', ['fee_structure_item_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'demand_items', 'users', ['updated_by'], ['id'], initially='DEFERRED', deferrable=True, use_alter=True)
    op.create_foreign_key(None, 'demand_items', 'admission_students', ['student_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'demand_items', 'users', ['created_by'], ['id'], initially='DEFERRED', deferrable=True, use_alter=True)


def downgrade() -> None:
    """Downgrade schema."""
    # demand_items reverses
    op.drop_constraint(None, 'demand_items', type_='foreignkey')
    op.drop_constraint(None, 'demand_items', type_='foreignkey')
    op.drop_constraint(None, 'demand_items', type_='foreignkey')
    op.drop_constraint(None, 'demand_items', type_='foreignkey')
    op.drop_constraint(None, 'demand_items', type_='foreignkey')
    op.drop_constraint(None, 'demand_items', type_='foreignkey')
    op.drop_index(op.f('ix_demand_items_student_id'), table_name='demand_items')
    op.drop_index(op.f('ix_demand_items_invoice_id'), table_name='demand_items')
    op.drop_index(op.f('ix_demand_items_fee_structure_item_id'), table_name='demand_items')
    op.drop_index(op.f('ix_demand_items_fee_structure_id'), table_name='demand_items')
    op.drop_index(op.f('ix_demand_items_batch_id'), table_name='demand_items')
    op.drop_column('demand_items', 'deleted_by')
    op.drop_column('demand_items', 'updated_by')
    op.drop_column('demand_items', 'created_by')
    op.drop_column('demand_items', 'deleted_at')

    # demand_batches reverses
    op.drop_constraint(None, 'demand_batches', type_='foreignkey')
    op.drop_constraint(None, 'demand_batches', type_='foreignkey')
    op.drop_constraint(None, 'demand_batches', type_='foreignkey')
    op.drop_constraint(None, 'demand_batches', type_='foreignkey')
    op.drop_constraint(None, 'demand_batches', type_='foreignkey')
    op.drop_constraint(None, 'demand_batches', type_='foreignkey')
    op.drop_index(op.f('ix_demand_batches_institution_id'), table_name='demand_batches')
    op.drop_index(op.f('ix_demand_batches_fee_structure_id'), table_name='demand_batches')
    op.drop_index(op.f('ix_demand_batches_admission_year_id'), table_name='demand_batches')
    op.alter_column('demand_batches', 'generated_at',
               existing_type=sa.DateTime(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.drop_column('demand_batches', 'deleted_by')
    op.drop_column('demand_batches', 'updated_by')
    op.drop_column('demand_batches', 'created_by')
    op.drop_column('demand_batches', 'deleted_at')
