import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.users.models
import app.execution.models
import app.strategies.models
import app.wallets.models
import app.subscriptions.models
import app.brokers.models

import asyncio
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.strategies.models import Strategy, StrategyExecution, StrategyExecutionLeg
from app.execution.models import StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent

async def inspect_paper_executions():
    print("=" * 80)
    print("📋 ZENALGO LIVE PAPER TRADING EXECUTION INSPECTOR")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        # 1. Fetch all Executions
        stmt = (
            select(StrategyExecution)
            .join(Strategy, StrategyExecution.strategy_id == Strategy.id)
            .order_by(StrategyExecution.id.desc())
            .limit(10)
            .options(
                selectinload(StrategyExecution.legs),
                selectinload(StrategyExecution.strategy),
                selectinload(StrategyExecution.strategy_version)
            )
        )
        res = await db.execute(stmt)
        executions = list(res.scalars().all())

        if not executions:
            print("\n❌ No trading executions found yet.")
            print("   Run: `python3 scratch/simulate_strategy_execution.py` to place a paper order.")
            return

        print(f"\nFound {len(executions)} Recent Trading Execution(s):\n")

        for idx, ex in enumerate(executions, 1):
            strat_name = ex.strategy.name if ex.strategy else f"Strategy #{ex.strategy_id}"
            strat_mode = ex.strategy.mode if ex.strategy else "PAPER"
            capital_val = ex.strategy_version.capital if ex.strategy_version else "100000.00"
            print(f"[{idx}] EXECUTION ID: {ex.id}")
            print(f"    • Strategy: {strat_name} (ID: {ex.strategy_id}, Version: {ex.strategy_version_id})")
            print(f"    • Trading Mode: 📄 {strat_mode}")
            print(f"    • Execution Status: 🟢 {ex.status}")
            print(f"    • User ID: {ex.user_id}")
            print(f"    • Capital Allocation: ₹{capital_val}")
            print(f"    • Realized PnL: ₹{ex.realized_pnl or '0.00'}")
            print(f"    • Entry Time: {ex.entry_time}")
            print(f"    • Exit Time: {ex.exit_time or 'OPEN (Running)'}")
            
            if ex.legs:
                print(f"    • Executed Trade Legs ({len(ex.legs)}):")
                for leg in ex.legs:
                    print(f"      - Leg ID {leg.id}: Qty={leg.filled_quantity}/{leg.quantity} | Fill Price=₹{leg.price} | Status={leg.status} | Correlation={leg.correlation_id}")
            
            if ex.execution_logs:
                print(f"    • Execution Logs:")
                for line in ex.execution_logs.strip().split("\n"):
                    print(f"      {line}")
            print("-" * 80)

        # 2. Fetch User Audit Traces
        stmt_traces = (
            select(StrategyUserExecutionTrace)
            .order_by(StrategyUserExecutionTrace.id.desc())
            .limit(5)
            .options(selectinload(StrategyUserExecutionTrace.events))
        )
        res_traces = await db.execute(stmt_traces)
        traces = list(res_traces.scalars().all())

        if traces:
            print("\n🔍 RECENT SUBSCRIBER AUDIT TRACES (Proof of Execution & Timeline):")
            for t in traces:
                print(f"\n  • Trace ID: {t.id} | User ID: {t.user_id} | Status: {t.status} | Correlation: {t.correlation_id}")
                for ev in t.events:
                    print(f"    [{ev.created_at.strftime('%H:%M:%S')}] Step: {ev.step} -> Status: {ev.status} ({ev.message})")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(inspect_paper_executions())
