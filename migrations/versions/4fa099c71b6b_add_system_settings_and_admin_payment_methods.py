"""add_system_settings_and_admin_payment_methods

Revision ID: 4fa099c71b6b
Revises: 3fa099c71b6a
Create Date: 2026-09-11 16:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4fa099c71b6b'
down_revision: Union[str, Sequence[str], None] = '3fa099c71b6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'system_settings' not in tables:
        op.create_table(
            'system_settings',
            sa.Column('key', sa.String(length=100), primary_key=True, nullable=False),
            sa.Column('value', sa.Text(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_by', sa.String(length=255), nullable=True),
        )
        op.create_index(op.f('ix_system_settings_key'), 'system_settings', ['key'], unique=False)

    if 'admin_payment_methods' not in tables:
        op.create_table(
            'admin_payment_methods',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('method_type', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=100), nullable=False),
            sa.Column('bank_name', sa.String(length=100), nullable=True),
            sa.Column('account_number', sa.String(length=100), nullable=True),
            sa.Column('ifsc_code', sa.String(length=50), nullable=True),
            sa.Column('account_holder_name', sa.String(length=100), nullable=True),
            sa.Column('upi_id', sa.String(length=100), nullable=True),
            sa.Column('upi_qr_url', sa.String(length=500), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('display_order', sa.Integer(), server_default='0', nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'admin_payment_methods' in tables:
        op.drop_table('admin_payment_methods')

    if 'system_settings' in tables:
        op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
        op.drop_table('system_settings')
