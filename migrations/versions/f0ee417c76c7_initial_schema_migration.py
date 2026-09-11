"""Initial schema migration

Revision ID: f0ee417c76c7
Revises: 
Create Date: 2026-08-29 10:27:43.524931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f0ee417c76c7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_initial_schema() -> None:
    """Create initial baseline schema on a clean database using native Alembic operations."""
    # 1. users
    user_role = postgresql.ENUM('SUPER_ADMIN', 'ADMIN', 'TRADER', 'USER', 'PARTNER', name='user_role', create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table('users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', user_role, server_default='USER', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('referral_code', sa.String(length=50), nullable=False),
        sa.Column('referred_by_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('first_name', sa.String(length=50), nullable=True),
        sa.Column('last_name', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_referral_code'), 'users', ['referral_code'], unique=True)

    # 2. wallets
    op.create_table('wallets',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('balance', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
        sa.Column('version', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wallets_user_id'), 'wallets', ['user_id'], unique=True)

    # 3. wallet_transactions
    op.create_table('wallet_transactions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('wallet_id', sa.BigInteger(), sa.ForeignKey('wallets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('balance_before', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('reference_type', sa.String(length=100), nullable=True),
        sa.Column('reference_id', sa.String(length=255), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='COMPLETED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wallet_transactions_wallet_id'), 'wallet_transactions', ['wallet_id'], unique=False)
    op.create_index(op.f('ix_wallet_transactions_idempotency_key'), 'wallet_transactions', ['idempotency_key'], unique=True)

    # 4. plans
    op.create_table('plans',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('monthly_price', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
        sa.Column('gst_percentage', sa.Numeric(precision=5, scale=2), server_default='18.00', nullable=False),
        sa.Column('min_wallet_balance', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('max_active_strategies', sa.Integer(), nullable=True),
        sa.Column('max_strategy_executions_per_day', sa.Integer(), nullable=True),
        sa.Column('max_portfolio_capital', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('subscription_type', sa.String(length=30), server_default='MONTHLY', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_by_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plans_code'), 'plans', ['code'], unique=True)

    # 5. strategies
    op.create_table('strategies',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategy_type', sa.String(length=50), server_default='CUSTOM_MULTI_LEG', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='DRAFT', nullable=False),
        sa.Column('target_profit', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('stop_loss', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('trailing_stop_loss', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('allocated_capital', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('parameters', sa.Text(), nullable=True),
        sa.Column('mode', sa.String(length=30), server_default='PAPER', nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('is_prebuilt', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('current_version_id', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategies_user_id'), 'strategies', ['user_id'], unique=False)
    op.create_index(op.f('ix_strategies_status'), 'strategies', ['status'], unique=False)

    # 6. strategy_versions
    op.create_table('strategy_versions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_id', sa.BigInteger(), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('underlying', sa.String(length=50), nullable=False),
        sa.Column('capital', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('trading_type', sa.String(length=30), server_default='INTRADAY', nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_id', 'version_number', name='uk_strategy_version')
    )
    op.create_foreign_key('fk_strategies_current_version_id', 'strategies', 'strategy_versions', ['current_version_id'], ['id'], ondelete='SET NULL', use_alter=True)

    # 7. plan_features
    op.create_table('plan_features',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.BigInteger(), sa.ForeignKey('plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature_code', sa.String(length=100), nullable=False),
        sa.Column('feature_value', sa.String(length=255), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_by_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'feature_code', name='uq_plan_feature_code')
    )

    # 8. plan_strategy_access
    op.create_table('plan_strategy_access',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.BigInteger(), sa.ForeignKey('plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_id', sa.BigInteger(), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_by_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'strategy_id', name='uq_plan_strategy_access')
    )
    op.create_index(op.f('ix_plan_strategy_access_plan_id'), 'plan_strategy_access', ['plan_id'], unique=False)

    # 9. subscriptions
    op.create_table('subscriptions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('plan_id', sa.BigInteger(), sa.ForeignKey('plans.id'), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancellation_reason', sa.String(length=500), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('payment_provider', sa.String(length=30), nullable=True),
        sa.Column('external_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_status'), 'subscriptions', ['status'], unique=False)
    op.create_index(op.f('ix_subscriptions_current_period_end'), 'subscriptions', ['current_period_end'], unique=False)

    # 10. subscription_payments
    op.create_table('subscription_payments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('subscription_id', sa.BigInteger(), sa.ForeignKey('subscriptions.id'), nullable=True),
        sa.Column('plan_id', sa.BigInteger(), sa.ForeignKey('plans.id'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('gst_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
        sa.Column('payment_provider', sa.String(length=50), server_default='MANUAL_UTR', nullable=False),
        sa.Column('payment_mode', sa.String(length=50), server_default='UPI', nullable=False),
        sa.Column('utr_number', sa.String(length=255), nullable=True),
        sa.Column('user_remarks', sa.String(length=500), nullable=True),
        sa.Column('admin_notes', sa.String(length=500), nullable=True),
        sa.Column('approved_by_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_payment_id', sa.String(length=255), nullable=True),
        sa.Column('provider_order_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='PENDING_APPROVAL', nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), unique=True, nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_payments_user_id'), 'subscription_payments', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscription_payments_provider_payment_id'), 'subscription_payments', ['provider_payment_id'], unique=False)
    op.create_index(op.f('ix_subscription_payments_utr_number'), 'subscription_payments', ['utr_number'], unique=False)

    # 11. subscription_events
    op.create_table('subscription_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('subscription_id', sa.BigInteger(), sa.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('old_plan_id', sa.BigInteger(), nullable=True),
        sa.Column('new_plan_id', sa.BigInteger(), nullable=True),
        sa.Column('old_status', sa.String(length=30), nullable=True),
        sa.Column('new_status', sa.String(length=30), nullable=True),
        sa.Column('reference_id', sa.String(length=255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_events_subscription_id'), 'subscription_events', ['subscription_id'], unique=False)

    # 12. user_daily_strategy_usage
    op.create_table('user_daily_strategy_usage',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('trading_date', sa.Date(), nullable=False),
        sa.Column('strategy_execution_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'trading_date', name='uq_user_daily_usage')
    )
    op.create_index(op.f('ix_user_daily_strategy_usage_user_id'), 'user_daily_strategy_usage', ['user_id'], unique=False)

    # 13. strategy_legs
    op.create_table('strategy_legs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('segment', sa.String(length=20), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),
        sa.Column('strike_selection', sa.String(length=50), nullable=False),
        sa.Column('strike_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('expiry', sa.String(length=50), nullable=False),
        sa.Column('lots', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.String(length=50), server_default='NONE', nullable=False),
        sa.Column('target_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('stop_loss_type', sa.String(length=50), server_default='NONE', nullable=False),
        sa.Column('stop_loss_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('trailing_sl_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('trailing_sl_activate_type', sa.String(length=50), nullable=True),
        sa.Column('trailing_sl_activate_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('trailing_sl_increase_by', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('trailing_sl_by', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_version_id', 'sequence', name='uk_version_sequence')
    )

    # 14. strategy_entry_settings
    op.create_table('strategy_entry_settings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entry_time', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 15. strategy_entry_days
    op.create_table('strategy_entry_days',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day_of_week', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_version_id', 'day_of_week', name='uk_version_day')
    )

    # 16. strategy_exit_settings
    op.create_table('strategy_exit_settings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('profit_mtm_type', sa.String(length=50), server_default='NONE', nullable=False),
        sa.Column('profit_mtm_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('stop_loss_mtm_type', sa.String(length=50), server_default='NONE', nullable=False),
        sa.Column('stop_loss_mtm_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('exit_time', sa.String(length=10), nullable=False),
        sa.Column('exit_on_expiry', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('exit_after_entry_type', sa.String(length=50), server_default='NONE', nullable=False),
        sa.Column('exit_after_entry_value', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 17. strategy_signals
    op.create_table('strategy_signals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_id', sa.BigInteger(), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trading_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('entry_time', sa.String(length=10), server_default='00:00', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_id', 'strategy_version_id', 'trading_date', 'entry_time', name='uk_strategy_version_date_time')
    )
    op.create_index(op.f('ix_strategy_signals_strategy_id'), 'strategy_signals', ['strategy_id'], unique=False)

    # 18. strategy_execution_batches
    op.create_table('strategy_execution_batches',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('signal_id', sa.BigInteger(), sa.ForeignKey('strategy_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_id', sa.BigInteger(), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trading_date', sa.Date(), nullable=False),
        sa.Column('total_users', sa.Integer(), server_default='0', nullable=False),
        sa.Column('eligible_users', sa.Integer(), server_default='0', nullable=False),
        sa.Column('rejected_users', sa.Integer(), server_default='0', nullable=False),
        sa.Column('execution_started_users', sa.Integer(), server_default='0', nullable=False),
        sa.Column('successful_users', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_users', sa.Integer(), server_default='0', nullable=False),
        sa.Column('not_executed_users', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategy_execution_batches_strategy_id'), 'strategy_execution_batches', ['strategy_id'], unique=False)

    # 19. strategy_user_execution_traces
    op.create_table('strategy_user_execution_traces',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('execution_batch_id', sa.BigInteger(), sa.ForeignKey('strategy_execution_batches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('signal_id', sa.BigInteger(), sa.ForeignKey('strategy_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_id', sa.BigInteger(), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_id', sa.BigInteger(), nullable=True),
        sa.Column('broker_account_id', sa.BigInteger(), nullable=True),
        sa.Column('broker', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('eligibility_status', sa.String(length=50), nullable=True),
        sa.Column('execution_status', sa.String(length=50), nullable=True),
        sa.Column('failure_code', sa.String(length=100), nullable=True),
        sa.Column('failure_reason', sa.String(length=500), nullable=True),
        sa.Column('rejection_code', sa.String(length=100), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('current_step', sa.String(length=100), nullable=True),
        sa.Column('correlation_id', sa.String(length=255), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('signal_id', 'user_id', name='uq_signal_user_execution_trace')
    )
    op.create_index(op.f('ix_strategy_user_execution_traces_execution_batch_id'), 'strategy_user_execution_traces', ['execution_batch_id'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_signal_id'), 'strategy_user_execution_traces', ['signal_id'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_user_id'), 'strategy_user_execution_traces', ['user_id'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_status'), 'strategy_user_execution_traces', ['status'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_correlation_id'), 'strategy_user_execution_traces', ['correlation_id'], unique=False)

    # 20. strategy_execution_trace_events
    op.create_table('strategy_execution_trace_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('execution_trace_id', sa.BigInteger(), sa.ForeignKey('strategy_user_execution_traces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('message', sa.String(length=1000), nullable=True),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategy_execution_trace_events_execution_trace_id'), 'strategy_execution_trace_events', ['execution_trace_id'], unique=False)

    # 21. strategy_executions
    op.create_table('strategy_executions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_id', sa.BigInteger(), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_version_id', sa.BigInteger(), sa.ForeignKey('strategy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_trace_id', sa.BigInteger(), sa.ForeignKey('strategy_user_execution_traces.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='RUNNING', nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('unrealized_pnl', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('execution_logs', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategy_executions_strategy_id'), 'strategy_executions', ['strategy_id'], unique=False)
    op.create_index(op.f('ix_strategy_executions_user_id'), 'strategy_executions', ['user_id'], unique=False)

    # 22. strategy_execution_legs
    op.create_table('strategy_execution_legs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_execution_id', sa.BigInteger(), sa.ForeignKey('strategy_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_leg_id', sa.BigInteger(), sa.ForeignKey('strategy_legs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_order_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='PENDING', nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 23. user_holdings
    op.create_table('user_holdings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_name', sa.String(length=50), server_default='DHAN', nullable=False),
        sa.Column('trading_symbol', sa.String(length=100), nullable=False),
        sa.Column('security_id', sa.String(length=50), nullable=True),
        sa.Column('isin', sa.String(length=50), nullable=False),
        sa.Column('exchange', sa.String(length=20), server_default='NSE', nullable=True),
        sa.Column('total_qty', sa.Integer(), server_default='0', nullable=False),
        sa.Column('dp_qty', sa.Integer(), server_default='0', nullable=True),
        sa.Column('t1_qty', sa.Integer(), server_default='0', nullable=True),
        sa.Column('available_qty', sa.Integer(), server_default='0', nullable=True),
        sa.Column('collateral_qty', sa.Integer(), server_default='0', nullable=True),
        sa.Column('avg_cost_price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('last_traded_price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'broker_name', 'isin', name='uk_user_holdings_user_broker_isin')
    )
    op.create_index(op.f('ix_user_holdings_user_id'), 'user_holdings', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_holdings_trading_symbol'), 'user_holdings', ['trading_symbol'], unique=False)

    # 24. user_positions
    op.create_table('user_positions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_name', sa.String(length=50), server_default='DHAN', nullable=False),
        sa.Column('trading_symbol', sa.String(length=100), nullable=False),
        sa.Column('security_id', sa.String(length=50), nullable=True),
        sa.Column('position_type', sa.String(length=50), server_default='INTRADAY', nullable=False),
        sa.Column('exchange_segment', sa.String(length=50), nullable=True),
        sa.Column('product_type', sa.String(length=50), nullable=True),
        sa.Column('net_qty', sa.Integer(), server_default='0', nullable=False),
        sa.Column('buy_qty', sa.Integer(), server_default='0', nullable=True),
        sa.Column('sell_qty', sa.Integer(), server_default='0', nullable=True),
        sa.Column('buy_avg', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('sell_avg', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('realized_profit', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('unrealized_profit', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'broker_name', 'security_id', 'position_type', name='uk_user_positions_user_sec_pos')
    )
    op.create_index(op.f('ix_user_positions_user_id'), 'user_positions', ['user_id'], unique=False)

    # 25. user_orders
    op.create_table('user_orders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_name', sa.String(length=50), server_default='DHAN', nullable=False),
        sa.Column('broker_order_id', sa.String(length=100), nullable=False),
        sa.Column('correlation_id', sa.String(length=100), nullable=True),
        sa.Column('trading_symbol', sa.String(length=100), nullable=True),
        sa.Column('security_id', sa.String(length=50), nullable=True),
        sa.Column('exchange_segment', sa.String(length=50), nullable=True),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('order_type', sa.String(length=50), nullable=False),
        sa.Column('product_type', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('disclosed_quantity', sa.Integer(), server_default='0', nullable=True),
        sa.Column('price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('trigger_price', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('order_status', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('order_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'broker_name', 'broker_order_id', name='uk_user_orders_user_order_id')
    )
    op.create_index(op.f('ix_user_orders_user_id'), 'user_orders', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_orders_order_status'), 'user_orders', ['order_status'], unique=False)

    # 26. user_trades
    op.create_table('user_trades',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_name', sa.String(length=50), server_default='DHAN', nullable=False),
        sa.Column('broker_trade_id', sa.String(length=100), nullable=False),
        sa.Column('broker_order_id', sa.String(length=100), nullable=True),
        sa.Column('trading_symbol', sa.String(length=100), nullable=True),
        sa.Column('security_id', sa.String(length=50), nullable=True),
        sa.Column('exchange_segment', sa.String(length=50), nullable=True),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('traded_quantity', sa.Integer(), nullable=False),
        sa.Column('traded_price', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('traded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'broker_name', 'broker_trade_id', name='uk_user_trades_user_trade_id')
    )
    op.create_index(op.f('ix_user_trades_user_id'), 'user_trades', ['user_id'], unique=False)

    # 27. user_fund_snapshots
    op.create_table('user_fund_snapshots',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_name', sa.String(length=50), server_default='DHAN', nullable=False),
        sa.Column('dhan_client_id', sa.String(length=50), nullable=True),
        sa.Column('available_balance', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('sod_limit', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('collateral_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('receiveable_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('utilized_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('blocked_payout_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('withdrawable_balance', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=True),
        sa.Column('snapshot_date', sa.Date(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'broker_name', 'snapshot_date', name='uk_user_funds_user_date')
    )
    op.create_index(op.f('ix_user_fund_snapshots_user_id'), 'user_fund_snapshots', ['user_id'], unique=False)

    # 28. dhan_broker_sessions
    op.create_table('dhan_broker_sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dhan_client_id', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('mobile_no', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
        sa.Column('expiry_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connection_date', sa.Date(), server_default=sa.text('now()'), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dhan_broker_sessions_user_id'), 'dhan_broker_sessions', ['user_id'], unique=True)
    op.create_index(op.f('ix_dhan_broker_sessions_dhan_client_id'), 'dhan_broker_sessions', ['dhan_client_id'], unique=False)
    op.create_index(op.f('ix_dhan_broker_sessions_status'), 'dhan_broker_sessions', ['status'], unique=False)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if not tables or 'users' not in tables:
        _create_initial_schema()
        return

    op.drop_index(op.f('flyway_schema_history_s_idx'), table_name='flyway_schema_history', if_exists=True)
    op.drop_table('flyway_schema_history', if_exists=True)

    op.drop_constraint(op.f('dhan_broker_sessions_user_id_key'), 'dhan_broker_sessions', type_='unique')
    op.drop_index(op.f('idx_dhan_broker_sessions_conn_date'), table_name='dhan_broker_sessions')
    op.drop_index(op.f('idx_dhan_broker_sessions_dhan_client_id'), table_name='dhan_broker_sessions')
    op.drop_index(op.f('idx_dhan_broker_sessions_status'), table_name='dhan_broker_sessions')
    op.drop_index(op.f('idx_dhan_broker_sessions_user_id'), table_name='dhan_broker_sessions')
    op.create_index(op.f('ix_dhan_broker_sessions_dhan_client_id'), 'dhan_broker_sessions', ['dhan_client_id'], unique=False)
    op.create_index(op.f('ix_dhan_broker_sessions_status'), 'dhan_broker_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_dhan_broker_sessions_user_id'), 'dhan_broker_sessions', ['user_id'], unique=True)
    op.drop_table_comment(
        'dhan_broker_sessions',
        existing_comment='Stores Dhan HQ access tokens, user metadata, and credentials. One row per platform user.',
        schema=None
    )
    op.drop_constraint(op.f('plan_features_plan_id_feature_code_key'), 'plan_features', type_='unique')
    op.create_unique_constraint('uq_plan_feature_code', 'plan_features', ['plan_id', 'feature_code'])
    op.drop_index(op.f('idx_plan_strategy_access_plan_strategy'), table_name='plan_strategy_access')
    op.drop_constraint(op.f('plan_strategy_access_plan_id_strategy_id_key'), 'plan_strategy_access', type_='unique')
    op.create_index(op.f('ix_plan_strategy_access_plan_id'), 'plan_strategy_access', ['plan_id'], unique=False)
    op.create_unique_constraint('uq_plan_strategy_access', 'plan_strategy_access', ['plan_id', 'strategy_id'])
    op.create_foreign_key(None, 'plan_strategy_access', 'strategies', ['strategy_id'], ['id'], ondelete='CASCADE')
    op.alter_column('plans', 'description',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               existing_nullable=True)
    op.drop_constraint(op.f('plans_code_key'), 'plans', type_='unique')
    op.create_index(op.f('ix_plans_code'), 'plans', ['code'], unique=True)
    op.drop_index(op.f('idx_strategies_status'), table_name='strategies')
    op.drop_index(op.f('idx_strategies_user_id'), table_name='strategies')
    op.create_index(op.f('ix_strategies_status'), 'strategies', ['status'], unique=False)
    op.create_index(op.f('ix_strategies_user_id'), 'strategies', ['user_id'], unique=False)
    op.drop_column('strategies', 'created_at')
    op.drop_column('strategies', 'updated_at')
    op.create_index(op.f('ix_strategy_execution_batches_strategy_id'), 'strategy_execution_batches', ['strategy_id'], unique=False)
    op.create_index(op.f('ix_strategy_execution_trace_events_execution_trace_id'), 'strategy_execution_trace_events', ['execution_trace_id'], unique=False)
    op.create_index(op.f('ix_strategy_executions_strategy_id'), 'strategy_executions', ['strategy_id'], unique=False)
    op.create_index(op.f('ix_strategy_executions_user_id'), 'strategy_executions', ['user_id'], unique=False)
    op.create_index(op.f('ix_strategy_signals_strategy_id'), 'strategy_signals', ['strategy_id'], unique=False)
    op.drop_index(op.f('idx_execution_trace_batch'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('idx_execution_trace_correlation'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('idx_execution_trace_signal'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('idx_execution_trace_status'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('idx_execution_trace_user'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('uq_signal_user_execution_trace'), table_name='strategy_user_execution_traces')
    op.create_unique_constraint('uq_signal_user_execution_trace', 'strategy_user_execution_traces', ['signal_id', 'user_id'])
    op.create_index(op.f('ix_strategy_user_execution_traces_correlation_id'), 'strategy_user_execution_traces', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_execution_batch_id'), 'strategy_user_execution_traces', ['execution_batch_id'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_signal_id'), 'strategy_user_execution_traces', ['signal_id'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_status'), 'strategy_user_execution_traces', ['status'], unique=False)
    op.create_index(op.f('ix_strategy_user_execution_traces_user_id'), 'strategy_user_execution_traces', ['user_id'], unique=False)
    op.drop_index(op.f('idx_subscription_events_subscription_id'), table_name='subscription_events')
    op.create_index(op.f('ix_subscription_events_subscription_id'), 'subscription_events', ['subscription_id'], unique=False)
    op.drop_index(op.f('idx_subscription_payments_provider_payment_id'), table_name='subscription_payments')
    op.drop_index(op.f('idx_subscription_payments_user_id'), table_name='subscription_payments')
    op.create_index(op.f('ix_subscription_payments_provider_payment_id'), 'subscription_payments', ['provider_payment_id'], unique=False)
    op.create_index(op.f('ix_subscription_payments_user_id'), 'subscription_payments', ['user_id'], unique=False)
    op.drop_index(op.f('idx_subscriptions_current_period_end'), table_name='subscriptions')
    op.drop_index(op.f('idx_subscriptions_status'), table_name='subscriptions')
    op.drop_index(op.f('idx_subscriptions_user_id'), table_name='subscriptions')
    op.create_index(op.f('ix_subscriptions_current_period_end'), 'subscriptions', ['current_period_end'], unique=False)
    op.create_index(op.f('ix_subscriptions_status'), 'subscriptions', ['status'], unique=False)
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.drop_index(op.f('idx_user_daily_strategy_usage_user_date'), table_name='user_daily_strategy_usage')
    op.drop_constraint(op.f('user_daily_strategy_usage_user_id_trading_date_key'), 'user_daily_strategy_usage', type_='unique')
    op.create_index(op.f('ix_user_daily_strategy_usage_user_id'), 'user_daily_strategy_usage', ['user_id'], unique=False)
    op.create_unique_constraint('uq_user_daily_usage', 'user_daily_strategy_usage', ['user_id', 'trading_date'])
    op.drop_index(op.f('idx_user_fund_snapshots_user_date'), table_name='user_fund_snapshots')
    op.create_index(op.f('ix_user_fund_snapshots_user_id'), 'user_fund_snapshots', ['user_id'], unique=False)
    op.drop_index(op.f('idx_user_holdings_symbol'), table_name='user_holdings')
    op.drop_index(op.f('idx_user_holdings_user_id'), table_name='user_holdings')
    op.create_index(op.f('ix_user_holdings_trading_symbol'), 'user_holdings', ['trading_symbol'], unique=False)
    op.create_index(op.f('ix_user_holdings_user_id'), 'user_holdings', ['user_id'], unique=False)
    op.drop_index(op.f('idx_user_orders_status'), table_name='user_orders')
    op.drop_index(op.f('idx_user_orders_user_id'), table_name='user_orders')
    op.create_index(op.f('ix_user_orders_order_status'), 'user_orders', ['order_status'], unique=False)
    op.create_index(op.f('ix_user_orders_user_id'), 'user_orders', ['user_id'], unique=False)
    op.drop_index(op.f('idx_user_positions_user_id'), table_name='user_positions')
    op.create_index(op.f('ix_user_positions_user_id'), 'user_positions', ['user_id'], unique=False)
    op.drop_index(op.f('idx_user_trades_user_id'), table_name='user_trades')
    op.create_index(op.f('ix_user_trades_user_id'), 'user_trades', ['user_id'], unique=False)
    op.drop_index(op.f('idx_users_email'), table_name='users')
    op.drop_index(op.f('idx_users_referral_code'), table_name='users')
    op.drop_constraint(op.f('users_email_key'), 'users', type_='unique')
    op.drop_constraint(op.f('users_referral_code_key'), 'users', type_='unique')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_referral_code'), 'users', ['referral_code'], unique=True)
    op.drop_index(op.f('idx_wallet_transactions_idempotency_key'), table_name='wallet_transactions')
    op.drop_index(op.f('idx_wallet_transactions_wallet_id'), table_name='wallet_transactions')
    op.drop_constraint(op.f('wallet_transactions_idempotency_key_key'), 'wallet_transactions', type_='unique')
    op.create_index(op.f('ix_wallet_transactions_idempotency_key'), 'wallet_transactions', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_wallet_transactions_wallet_id'), 'wallet_transactions', ['wallet_id'], unique=False)
    op.drop_constraint(op.f('wallet_transactions_wallet_id_fkey'), 'wallet_transactions', type_='foreignkey')
    op.create_foreign_key(None, 'wallet_transactions', 'wallets', ['wallet_id'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('idx_wallets_user_id'), table_name='wallets')
    op.drop_constraint(op.f('wallets_user_id_key'), 'wallets', type_='unique')
    op.create_index(op.f('ix_wallets_user_id'), 'wallets', ['user_id'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_wallets_user_id'), table_name='wallets')
    op.create_unique_constraint(op.f('wallets_user_id_key'), 'wallets', ['user_id'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('idx_wallets_user_id'), 'wallets', ['user_id'], unique=False)
    op.drop_constraint(None, 'wallet_transactions', type_='foreignkey')
    op.create_foreign_key(op.f('wallet_transactions_wallet_id_fkey'), 'wallet_transactions', 'wallets', ['wallet_id'], ['id'])
    op.drop_index(op.f('ix_wallet_transactions_wallet_id'), table_name='wallet_transactions')
    op.drop_index(op.f('ix_wallet_transactions_idempotency_key'), table_name='wallet_transactions')
    op.create_unique_constraint(op.f('wallet_transactions_idempotency_key_key'), 'wallet_transactions', ['idempotency_key'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('idx_wallet_transactions_wallet_id'), 'wallet_transactions', ['wallet_id'], unique=False)
    op.create_index(op.f('idx_wallet_transactions_idempotency_key'), 'wallet_transactions', ['idempotency_key'], unique=False)
    op.drop_index(op.f('ix_users_referral_code'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_unique_constraint(op.f('users_referral_code_key'), 'users', ['referral_code'], postgresql_nulls_not_distinct=False)
    op.create_unique_constraint(op.f('users_email_key'), 'users', ['email'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('idx_users_referral_code'), 'users', ['referral_code'], unique=False)
    op.create_index(op.f('idx_users_email'), 'users', ['email'], unique=False)
    op.drop_index(op.f('ix_user_trades_user_id'), table_name='user_trades')
    op.create_index(op.f('idx_user_trades_user_id'), 'user_trades', ['user_id'], unique=False)
    op.drop_index(op.f('ix_user_positions_user_id'), table_name='user_positions')
    op.create_index(op.f('idx_user_positions_user_id'), 'user_positions', ['user_id'], unique=False)
    op.drop_index(op.f('ix_user_orders_user_id'), table_name='user_orders')
    op.drop_index(op.f('ix_user_orders_order_status'), table_name='user_orders')
    op.create_index(op.f('idx_user_orders_user_id'), 'user_orders', ['user_id'], unique=False)
    op.create_index(op.f('idx_user_orders_status'), 'user_orders', ['order_status'], unique=False)
    op.drop_index(op.f('ix_user_holdings_user_id'), table_name='user_holdings')
    op.drop_index(op.f('ix_user_holdings_trading_symbol'), table_name='user_holdings')
    op.create_index(op.f('idx_user_holdings_user_id'), 'user_holdings', ['user_id'], unique=False)
    op.create_index(op.f('idx_user_holdings_symbol'), 'user_holdings', ['trading_symbol'], unique=False)
    op.drop_index(op.f('ix_user_fund_snapshots_user_id'), table_name='user_fund_snapshots')
    op.create_index(op.f('idx_user_fund_snapshots_user_date'), 'user_fund_snapshots', ['user_id', 'snapshot_date'], unique=False)
    op.drop_constraint('uq_user_daily_usage', 'user_daily_strategy_usage', type_='unique')
    op.drop_index(op.f('ix_user_daily_strategy_usage_user_id'), table_name='user_daily_strategy_usage')
    op.create_unique_constraint(op.f('user_daily_strategy_usage_user_id_trading_date_key'), 'user_daily_strategy_usage', ['user_id', 'trading_date'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('idx_user_daily_strategy_usage_user_date'), 'user_daily_strategy_usage', ['user_id', 'trading_date'], unique=False)
    op.drop_index(op.f('ix_subscriptions_user_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_status'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_current_period_end'), table_name='subscriptions')
    op.create_index(op.f('idx_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('idx_subscriptions_status'), 'subscriptions', ['status'], unique=False)
    op.create_index(op.f('idx_subscriptions_current_period_end'), 'subscriptions', ['current_period_end'], unique=False)
    op.drop_index(op.f('ix_subscription_payments_user_id'), table_name='subscription_payments')
    op.drop_index(op.f('ix_subscription_payments_provider_payment_id'), table_name='subscription_payments')
    op.create_index(op.f('idx_subscription_payments_user_id'), 'subscription_payments', ['user_id'], unique=False)
    op.create_index(op.f('idx_subscription_payments_provider_payment_id'), 'subscription_payments', ['provider_payment_id'], unique=False)
    op.drop_index(op.f('ix_subscription_events_subscription_id'), table_name='subscription_events')
    op.create_index(op.f('idx_subscription_events_subscription_id'), 'subscription_events', ['subscription_id'], unique=False)
    op.drop_index(op.f('ix_strategy_user_execution_traces_user_id'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('ix_strategy_user_execution_traces_status'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('ix_strategy_user_execution_traces_signal_id'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('ix_strategy_user_execution_traces_execution_batch_id'), table_name='strategy_user_execution_traces')
    op.drop_index(op.f('ix_strategy_user_execution_traces_correlation_id'), table_name='strategy_user_execution_traces')
    op.drop_constraint('uq_signal_user_execution_trace', 'strategy_user_execution_traces', type_='unique')
    op.create_index(op.f('uq_signal_user_execution_trace'), 'strategy_user_execution_traces', ['signal_id', 'user_id'], unique=True)
    op.create_index(op.f('idx_execution_trace_user'), 'strategy_user_execution_traces', ['user_id'], unique=False)
    op.create_index(op.f('idx_execution_trace_status'), 'strategy_user_execution_traces', ['status'], unique=False)
    op.create_index(op.f('idx_execution_trace_signal'), 'strategy_user_execution_traces', ['signal_id'], unique=False)
    op.create_index(op.f('idx_execution_trace_correlation'), 'strategy_user_execution_traces', ['correlation_id'], unique=False)
    op.create_index(op.f('idx_execution_trace_batch'), 'strategy_user_execution_traces', ['execution_batch_id'], unique=False)
    op.drop_index(op.f('ix_strategy_signals_strategy_id'), table_name='strategy_signals')
    op.drop_index(op.f('ix_strategy_executions_user_id'), table_name='strategy_executions')
    op.drop_index(op.f('ix_strategy_executions_strategy_id'), table_name='strategy_executions')
    op.drop_index(op.f('ix_strategy_execution_trace_events_execution_trace_id'), table_name='strategy_execution_trace_events')
    op.drop_index(op.f('ix_strategy_execution_batches_strategy_id'), table_name='strategy_execution_batches')
    op.add_column('strategies', sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False))
    op.add_column('strategies', sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False))
    op.drop_index(op.f('ix_strategies_user_id'), table_name='strategies')
    op.drop_index(op.f('ix_strategies_status'), table_name='strategies')
    op.create_index(op.f('idx_strategies_user_id'), 'strategies', ['user_id'], unique=False)
    op.create_index(op.f('idx_strategies_status'), 'strategies', ['status'], unique=False)
    op.drop_index(op.f('ix_plans_code'), table_name='plans')
    op.create_unique_constraint(op.f('plans_code_key'), 'plans', ['code'], postgresql_nulls_not_distinct=False)
    op.alter_column('plans', 'description',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               existing_nullable=True)
    op.drop_constraint(None, 'plan_strategy_access', type_='foreignkey')
    op.drop_constraint('uq_plan_strategy_access', 'plan_strategy_access', type_='unique')
    op.drop_index(op.f('ix_plan_strategy_access_plan_id'), table_name='plan_strategy_access')
    op.create_unique_constraint(op.f('plan_strategy_access_plan_id_strategy_id_key'), 'plan_strategy_access', ['plan_id', 'strategy_id'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('idx_plan_strategy_access_plan_strategy'), 'plan_strategy_access', ['plan_id', 'strategy_id'], unique=False)
    op.drop_constraint('uq_plan_feature_code', 'plan_features', type_='unique')
    op.create_unique_constraint(op.f('plan_features_plan_id_feature_code_key'), 'plan_features', ['plan_id', 'feature_code'], postgresql_nulls_not_distinct=False)
    op.create_table_comment(
        'dhan_broker_sessions',
        'Stores Dhan HQ access tokens, user metadata, and credentials. One row per platform user.',
        existing_comment=None,
        schema=None
    )
    op.drop_index(op.f('ix_dhan_broker_sessions_user_id'), table_name='dhan_broker_sessions')
    op.drop_index(op.f('ix_dhan_broker_sessions_status'), table_name='dhan_broker_sessions')
    op.drop_index(op.f('ix_dhan_broker_sessions_dhan_client_id'), table_name='dhan_broker_sessions')
    op.create_index(op.f('idx_dhan_broker_sessions_user_id'), 'dhan_broker_sessions', ['user_id'], unique=False)
    op.create_index(op.f('idx_dhan_broker_sessions_status'), 'dhan_broker_sessions', ['status'], unique=False)
    op.create_index(op.f('idx_dhan_broker_sessions_dhan_client_id'), 'dhan_broker_sessions', ['dhan_client_id'], unique=False)
    op.create_index(op.f('idx_dhan_broker_sessions_conn_date'), 'dhan_broker_sessions', ['user_id', 'connection_date'], unique=False)
    op.create_unique_constraint(op.f('dhan_broker_sessions_user_id_key'), 'dhan_broker_sessions', ['user_id'], postgresql_nulls_not_distinct=False)
    op.create_table('flyway_schema_history',
    sa.Column('installed_rank', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('version', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('description', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('type', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('script', sa.VARCHAR(length=1000), autoincrement=False, nullable=False),
    sa.Column('checksum', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('installed_by', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('installed_on', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('execution_time', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('success', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('installed_rank', name=op.f('flyway_schema_history_pk'))
    )
    op.create_index(op.f('flyway_schema_history_s_idx'), 'flyway_schema_history', ['success'], unique=False)
    # ### end Alembic commands ###
