"""Refactor broker architecture and create generic broker_accounts table

Revision ID: e1ff829b39d1
Revises: f0ee417c76c7
Create Date: 2026-08-29 12:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e1ff829b39d1'
down_revision: Union[str, Sequence[str], None] = 'f0ee417c76c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create broker_accounts table if missing
    if 'broker_accounts' not in tables:
        op.create_table(
            'broker_accounts',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('broker_code', sa.String(length=50), nullable=False),
            sa.Column('account_client_id', sa.String(length=100), nullable=False),
            sa.Column('account_name', sa.String(length=200), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('mobile_no', sa.String(length=50), nullable=True),
            sa.Column('auth_type', sa.String(length=50), server_default='TOKEN', nullable=False),
            sa.Column('encrypted_credentials', sa.Text(), nullable=True),
            sa.Column('expiry_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('primary_ip', sa.String(length=100), nullable=True),
            sa.Column('secondary_ip', sa.String(length=100), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
            sa.Column('connection_date', sa.Date(), server_default=sa.text('now()'), nullable=False),
            sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'broker_code', name='uk_user_broker_code')
        )

        op.create_index(op.f('ix_broker_accounts_user_id'), 'broker_accounts', ['user_id'], unique=False)
        op.create_index(op.f('ix_broker_accounts_broker_code'), 'broker_accounts', ['broker_code'], unique=False)
        op.create_index(op.f('ix_broker_accounts_account_client_id'), 'broker_accounts', ['account_client_id'], unique=False)
        op.create_index(op.f('ix_broker_accounts_status'), 'broker_accounts', ['status'], unique=False)

    # 2. Data Migration: Copy existing records from dhan_broker_sessions into broker_accounts if dhan_broker_sessions exists
    if 'dhan_broker_sessions' in tables:
        dhan_sessions = conn.execute(sa.text("SELECT user_id, dhan_client_id, email, mobile_no, status, expiry_time, connection_date, access_token FROM dhan_broker_sessions")).fetchall()
        
        for sess in dhan_sessions:
            conn.execute(
                sa.text(
                    "INSERT INTO broker_accounts (user_id, broker_code, account_client_id, email, mobile_no, status, expiry_time, connection_date, auth_type, encrypted_credentials) "
                    "VALUES (:user_id, 'DHAN', :client_id, :email, :mobile_no, :status, :expiry_time, :connection_date, 'TOKEN', :access_token) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "user_id": sess.user_id,
                    "client_id": sess.dhan_client_id,
                    "email": sess.email,
                    "mobile_no": sess.mobile_no,
                    "status": sess.status,
                    "expiry_time": sess.expiry_time,
                    "connection_date": sess.connection_date,
                    "access_token": sess.access_token
                }
            )
        op.drop_table('dhan_broker_sessions')

    # 4. Create user_daily_broker_connections table
    if 'user_daily_broker_connections' not in tables:
        op.create_table(
            'user_daily_broker_connections',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('connection_date', sa.Date(), nullable=False),
            sa.Column('broker_account_id', sa.BigInteger(), sa.ForeignKey('broker_accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('broker_code', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'connection_date', name='uk_user_daily_broker_date')
        )
        op.create_index(op.f('ix_user_daily_broker_connections_user_id'), 'user_daily_broker_connections', ['user_id'], unique=False)
        op.create_index(op.f('ix_user_daily_broker_connections_connection_date'), 'user_daily_broker_connections', ['connection_date'], unique=False)
        op.create_index(op.f('ix_user_daily_broker_connections_broker_account_id'), 'user_daily_broker_connections', ['broker_account_id'], unique=False)


def downgrade() -> None:
    op.drop_table('user_daily_broker_connections', if_exists=True)
    op.drop_table('broker_accounts', if_exists=True)

