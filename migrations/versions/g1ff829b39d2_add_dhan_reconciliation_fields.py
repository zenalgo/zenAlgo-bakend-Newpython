"""add_dhan_reconciliation_fields

Revision ID: g1ff829b39d2
Revises: e1ff829b39d1
Create Date: 2026-08-29 16:47:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'g1ff829b39d2'
down_revision: Union[str, None] = 'e1ff829b39d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # User orders updates
    uo_cols = [c['name'] for c in inspector.get_columns('user_orders')]
    if 'requested_quantity' not in uo_cols:
        op.add_column('user_orders', sa.Column('requested_quantity', sa.Integer(), nullable=True))
    if 'filled_quantity' not in uo_cols:
        op.add_column('user_orders', sa.Column('filled_quantity', sa.Integer(), server_default='0', nullable=True))
    if 'remaining_quantity' not in uo_cols:
        op.add_column('user_orders', sa.Column('remaining_quantity', sa.Integer(), server_default='0', nullable=True))
    if 'requested_price' not in uo_cols:
        op.add_column('user_orders', sa.Column('requested_price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True))
    if 'average_fill_price' not in uo_cols:
        op.add_column('user_orders', sa.Column('average_fill_price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True))
    if 'reconciliation_attempts' not in uo_cols:
        op.add_column('user_orders', sa.Column('reconciliation_attempts', sa.Integer(), server_default='0', nullable=True))
    if 'last_reconciled_at' not in uo_cols:
        op.add_column('user_orders', sa.Column('last_reconciled_at', sa.DateTime(timezone=True), nullable=True))
    if 'square_off_order_id' not in uo_cols:
        op.add_column('user_orders', sa.Column('square_off_order_id', sa.String(length=100), nullable=True))
    
    uo_constraints = [c['name'] for c in inspector.get_unique_constraints('user_orders')]
    if 'uk_user_orders_correlation_id' not in uo_constraints:
        op.create_unique_constraint('uk_user_orders_correlation_id', 'user_orders', ['correlation_id'])

    # Strategy execution legs updates
    sel_cols = [c['name'] for c in inspector.get_columns('strategy_execution_legs')]
    if 'correlation_id' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('correlation_id', sa.String(length=100), nullable=True))
    if 'requested_quantity' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('requested_quantity', sa.Integer(), nullable=True))
    if 'filled_quantity' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('filled_quantity', sa.Integer(), server_default='0', nullable=True))
    if 'remaining_quantity' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('remaining_quantity', sa.Integer(), server_default='0', nullable=True))
    if 'requested_price' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('requested_price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True))
    if 'average_fill_price' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('average_fill_price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True))
    if 'rejection_reason' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('rejection_reason', sa.Text(), nullable=True))
    if 'reconciliation_attempts' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('reconciliation_attempts', sa.Integer(), server_default='0', nullable=True))
    if 'last_reconciled_at' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('last_reconciled_at', sa.DateTime(timezone=True), nullable=True))
    if 'square_off_order_id' not in sel_cols:
        op.add_column('strategy_execution_legs', sa.Column('square_off_order_id', sa.String(length=100), nullable=True))

    sel_constraints = [c['name'] for c in inspector.get_unique_constraints('strategy_execution_legs')]
    if 'uk_strategy_execution_legs_correlation_id' not in sel_constraints:
        op.create_unique_constraint('uk_strategy_execution_legs_correlation_id', 'strategy_execution_legs', ['correlation_id'])

def downgrade() -> None:
    op.drop_constraint('uk_strategy_execution_legs_correlation_id', 'strategy_execution_legs', type_='unique')
    op.drop_column('strategy_execution_legs', 'square_off_order_id')
    op.drop_column('strategy_execution_legs', 'last_reconciled_at')
    op.drop_column('strategy_execution_legs', 'reconciliation_attempts')
    op.drop_column('strategy_execution_legs', 'rejection_reason')
    op.drop_column('strategy_execution_legs', 'average_fill_price')
    op.drop_column('strategy_execution_legs', 'requested_price')
    op.drop_column('strategy_execution_legs', 'remaining_quantity')
    op.drop_column('strategy_execution_legs', 'filled_quantity')
    op.drop_column('strategy_execution_legs', 'requested_quantity')
    op.drop_column('strategy_execution_legs', 'correlation_id')

    op.drop_constraint('uk_user_orders_correlation_id', 'user_orders', type_='unique')
    op.drop_column('user_orders', 'square_off_order_id')
    op.drop_column('user_orders', 'last_reconciled_at')
    op.drop_column('user_orders', 'reconciliation_attempts')
    op.drop_column('user_orders', 'average_fill_price')
    op.drop_column('user_orders', 'requested_price')
    op.drop_column('user_orders', 'remaining_quantity')
    op.drop_column('user_orders', 'filled_quantity')
    op.drop_column('user_orders', 'requested_quantity')
