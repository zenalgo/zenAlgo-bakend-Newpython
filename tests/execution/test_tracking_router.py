import pytest
from httpx import AsyncClient
from datetime import date
from decimal import Decimal

from app.strategies.models import Strategy, StrategyVersion
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent
from app.users.models import User, UserRole
from app.auth.service import hash_password

@pytest.fixture
async def active_admin(db_session):
    admin = User(
        email="admin_exec_tracking@example.com",
        password_hash=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True,
        referral_code="REF-ADM888"
    )
    db_session.add(admin)
    await db_session.flush()
    return admin

@pytest.mark.asyncio
async def test_execution_tracking_endpoints(client: AsyncClient, db_session, active_admin):
    # 1. Setup Test Data
    user = User(
        email="test_subscriber_1@example.com",
        password_hash="hash",
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-SUB123"
    )
    db_session.add(user)
    await db_session.flush()

    strategy = Strategy(
        name="Tracking Test Strategy",
        description="Testing batch and trace queries",
        status="ACTIVE_LIVE",
        mode="PAPER",
        user_id=user.id
    )
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(
        strategy_id=strategy.id,
        version_number=1,
        underlying="NIFTY",
        capital=Decimal("100000.00"),
        trading_type="INTRADAY"
    )
    db_session.add(version)
    await db_session.flush()

    strategy.current_version_id = version.id
    db_session.add(strategy)

    signal = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key="SIG-TRACK-TEST-1"
    )
    db_session.add(signal)
    await db_session.flush()

    batch = StrategyExecutionBatch(
        signal_id=signal.id,
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        total_users=10,
        eligible_users=8,
        rejected_users=2,
        execution_started_users=8,
        successful_users=7,
        failed_users=1,
        not_executed_users=0,
        status="COMPLETED_WITH_ERRORS"
    )
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=signal.id,
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        user_id=user.id,
        status="FAILED",
        current_step="BROKER_ORDER_PLACEMENT",
        failure_code="BROKER_SESSION_INVALID",
        failure_reason="Token expired at Dhan",
        correlation_id="TRACE-TRACK-TEST-1"
    )
    db_session.add(trace)
    await db_session.flush()

    event1 = StrategyExecutionTraceEvent(
        execution_trace_id=trace.id,
        step="USER_CHECK",
        status="SUCCESS",
        message="User is active"
    )
    event2 = StrategyExecutionTraceEvent(
        execution_trace_id=trace.id,
        step="BROKER_ORDER_PLACEMENT",
        status="FAILED",
        message="Token expired",
        error_code="BROKER_SESSION_INVALID"
    )
    db_session.add_all([event1, event2])
    await db_session.commit()

    # Authenticate admin
    login_res = await client.post("/api/v1/auth/admin/login", json={
        "email": "admin_exec_tracking@example.com",
        "password": "adminpass123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # A. Query Strategy Batches (How many users executed)
    r_batches = await client.get(f"/api/v1/admin/execution/strategies/{strategy.id}/batches", headers=headers)
    assert r_batches.status_code == 200
    data_batches = r_batches.json()
    assert data_batches["success"] is True
    assert len(data_batches["data"]) >= 1
    assert data_batches["data"][0]["totalUsers"] == 10
    assert data_batches["data"][0]["successfulUsers"] == 7
    assert data_batches["data"][0]["failedUsers"] == 1

    # B. Query Single Batch
    r_batch = await client.get(f"/api/v1/admin/execution/batches/{batch.id}", headers=headers)
    assert r_batch.status_code == 200
    assert r_batch.json()["data"]["batchId"] == batch.id

    # C. Query Batch User Traces
    r_traces = await client.get(f"/api/v1/admin/execution/batches/{batch.id}/traces", headers=headers)
    assert r_traces.status_code == 200
    traces_data = r_traces.json()["data"]
    assert len(traces_data) == 1
    assert traces_data[0]["userId"] == user.id
    assert traces_data[0]["status"] == "FAILED"

    # D. Query Particular User Trace Details with Timeline
    r_trace_detail = await client.get(f"/api/v1/admin/execution/traces/{trace.id}", headers=headers)
    assert r_trace_detail.status_code == 200
    trace_detail = r_trace_detail.json()["data"]
    assert trace_detail["userId"] == user.id
    assert trace_detail["failureCode"] == "BROKER_SESSION_INVALID"
    assert len(trace_detail["timeline"]) == 2

    # E. Query User Executions across strategies
    r_user_traces = await client.get(f"/api/v1/admin/execution/users/{user.id}/traces", headers=headers)
    assert r_user_traces.status_code == 200
    assert len(r_user_traces.json()["data"]) >= 1

    # F. Query Batch Failure Breakdown
    r_failures = await client.get(f"/api/v1/admin/execution/batches/{batch.id}/failures", headers=headers)
    assert r_failures.status_code == 200
    fail_data = r_failures.json()["data"]
    assert fail_data["totalFailures"] == 1
    assert fail_data["reasons"][0]["code"] == "BROKER_SESSION_INVALID"

    # G. Query Placed Paper Orders for Strategy
    from app.strategies.models import StrategyExecution, StrategyExecutionLeg, StrategyLeg
    strat_leg = StrategyLeg(strategy_version_id=version.id, sequence=1, segment="OPT", side="BUY", strike_selection="ATM", strike_value=Decimal("0.00"), lots=1, expiry="Weekly")
    db_session.add(strat_leg)
    await db_session.flush()

    exec_record = StrategyExecution(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        user_id=user.id,
        status="RUNNING",
        realized_pnl=Decimal("0.00"),
        unrealized_pnl=Decimal("250.00")
    )
    db_session.add(exec_record)
    await db_session.flush()

    exec_leg = StrategyExecutionLeg(
        strategy_execution_id=exec_record.id,
        strategy_leg_id=strat_leg.id,
        correlation_id="CORR-TEST-LEG-1",
        status="FILLED",
        quantity=50,
        filled_quantity=50,
        price=Decimal("100.00")
    )
    db_session.add(exec_leg)
    await db_session.commit()

    r_placed = await client.get(f"/api/v1/admin/execution/strategies/{strategy.id}/placed-orders", headers=headers)
    assert r_placed.status_code == 200
    placed_data = r_placed.json()["data"]
    assert len(placed_data) >= 1
    assert placed_data[0]["executionId"] == exec_record.id
    assert placed_data[0]["mode"] == "PAPER"
    assert placed_data[0]["status"] == "RUNNING"
    assert len(placed_data[0]["legs"]) == 1
    assert placed_data[0]["legs"][0]["price"] == 100.0

