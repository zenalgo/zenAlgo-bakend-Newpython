"""create_instruments_and_broker_mappings

Revision ID: 3fa099c71b6a
Revises: 229aa5279937
Create Date: 2026-09-03 14:50:22.996386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3fa099c71b6a'
down_revision: Union[str, Sequence[str], None] = '229aa5279937'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create instruments and broker_instruments tables."""
    op.create_table(
        'instruments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('sector', sa.String(length=100), nullable=False),
        sa.Column('instrument_type', sa.String(length=50), nullable=False, server_default='EQUITY'),
        sa.Column('is_fno', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_instruments_company_name'), 'instruments', ['company_name'], unique=False)
    op.create_index(op.f('ix_instruments_is_fno'), 'instruments', ['is_fno'], unique=False)
    op.create_index(op.f('ix_instruments_sector'), 'instruments', ['sector'], unique=False)
    op.create_index(op.f('ix_instruments_symbol'), 'instruments', ['symbol'], unique=True)

    op.create_table(
        'broker_instruments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('instrument_id', sa.BigInteger(), nullable=False),
        sa.Column('broker_code', sa.String(length=50), nullable=False),
        sa.Column('security_id', sa.String(length=50), nullable=False),
        sa.Column('exchange_segment', sa.String(length=50), nullable=False, server_default='NSE_EQ'),
        sa.Column('trading_symbol', sa.String(length=100), nullable=False),
        sa.Column('lot_size', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('tick_size', sa.Numeric(precision=10, scale=4), nullable=False, server_default='0.05'),
        sa.Column('extra_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['instrument_id'], ['instruments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instrument_id', 'broker_code', 'exchange_segment', name='uk_inst_broker_segment')
    )
    op.create_index(op.f('ix_broker_instruments_broker_code'), 'broker_instruments', ['broker_code'], unique=False)
    op.create_index(op.f('ix_broker_instruments_instrument_id'), 'broker_instruments', ['instrument_id'], unique=False)
    op.create_index(op.f('ix_broker_instruments_security_id'), 'broker_instruments', ['security_id'], unique=False)


def downgrade() -> None:
    """Drop instruments and broker_instruments tables."""
    op.drop_index(op.f('ix_broker_instruments_security_id'), table_name='broker_instruments')
    op.drop_index(op.f('ix_broker_instruments_instrument_id'), table_name='broker_instruments')
    op.drop_index(op.f('ix_broker_instruments_broker_code'), table_name='broker_instruments')
    op.drop_table('broker_instruments')

    op.drop_index(op.f('ix_instruments_symbol'), table_name='instruments')
    op.drop_index(op.f('ix_instruments_sector'), table_name='instruments')
    op.drop_index(op.f('ix_instruments_is_fno'), table_name='instruments')
    op.drop_index(op.f('ix_instruments_company_name'), table_name='instruments')
    op.drop_table('instruments')
