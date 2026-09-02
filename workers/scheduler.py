import asyncio
import logging
from datetime import datetime, date, time
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Pre-import all SQLAlchemy models to register them on Base metadata registry
import app.users.models
import app.execution.models
import app.strategies.models
import app.wallets.models
import app.subscriptions.models
import app.brokers.models

from app.core.database import AsyncSessionLocal
from app.strategies.models import Strategy, StrategyVersion, StrategyEntryDay
from app.execution.models import StrategySignal
from app.execution import service as exec_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

ZONE_KOLKATA = pytz.timezone("Asia/Kolkata")

# Static Indian Market Holidays 2026
INDIAN_HOLIDAYS_2026 = {
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 6),   # Holi
    date(2026, 4, 2),   # Good Friday
    date(2026, 5, 1),   # May Day
    date(2026, 8, 15),  # Independence Day
    date(2026, 10, 2),  # Gandhi Jayanti
    date(2026, 12, 25)  # Christmas
}

async def trigger_signal_if_absent(db: AsyncSession, strategy: Strategy, version: StrategyVersion, today: date, entry_time: str) -> None:
    """Inserts a StrategySignal if not already present, ensuring signal idempotency."""
    # Check signal existence
    stmt = select(StrategySignal).where(
        StrategySignal.strategy_id == strategy.id,
        StrategySignal.strategy_version_id == version.id,
        StrategySignal.trading_date == today,
        StrategySignal.entry_time == entry_time
    )
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        logger.info(f"Signal already exists for Strategy {strategy.id} version {version.id} at {entry_time} on {today}. Skipping.")
        return

    logger.info(f"Triggering new signal for Strategy {strategy.name} (ID {strategy.id}) at {entry_time}")
    
    # Savepoint insertion
    try:
        async with db.begin_nested():
            signal = StrategySignal(
                strategy_id=strategy.id,
                strategy_version_id=version.id,
                trading_date=today,
                entry_time=entry_time
            )
            db.add(signal)
            await db.flush()
        
        await db.commit() # Commit signal to database
        logger.info(f"Signal ID {signal.id} generated. Spawning batch execution...")
        
        # Call batch execution runner
        await exec_service.execute_signal_batch(signal.id)
    except Exception as ex:
        logger.error(f"Error triggering signal for Strategy {strategy.id}: {str(ex)}")

async def process_strategy_entry(strategy_id: int, today: date, current_time_str: str, day_name: str) -> None:
    """Evaluates and triggers entry logic for a single strategy in its own isolated database session."""
    async with AsyncSessionLocal() as db:
        try:
            stmt_strat = select(Strategy).where(Strategy.id == strategy_id)
            res_strat = await db.execute(stmt_strat)
            strategy = res_strat.scalar_one_or_none()
            if not strategy or not strategy.is_active or strategy.status != "ACTIVE_LIVE":
                return

            stmt_version = select(StrategyVersion).where(StrategyVersion.id == strategy.current_version_id)
            res_version = await db.execute(stmt_version)
            version = res_version.scalar_one_or_none()

            if not version:
                return

            from app.strategies.models import StrategyEntrySetting, StrategyEntryDay
            stmt_entry = select(StrategyEntrySetting).where(StrategyEntrySetting.strategy_version_id == version.id)
            res_entry = await db.execute(stmt_entry)
            version.entry_setting = res_entry.scalar_one_or_none()

            if not version.entry_setting:
                return

            entry_time = version.entry_setting.entry_time
            if current_time_str != entry_time:
                return

            stmt_days = select(StrategyEntryDay).where(StrategyEntryDay.strategy_version_id == version.id)
            res_days = await db.execute(stmt_days)
            version.entry_days = res_days.scalars().all()

            day_matches = any(day.day_of_week.upper() == day_name for day in version.entry_days)
            if not day_matches:
                return

            await trigger_signal_if_absent(db, strategy, version, today, entry_time)
        except Exception as ex:
            logger.error(f"Error checking strategy {strategy_id} in scheduler: {str(ex)}")

async def check_and_trigger_strategies() -> None:
    """Scheduler minute-tick job. Applies trading day, time, and timezone rules in parallel."""
    now_ist = datetime.now(ZONE_KOLKATA)
    today = now_ist.date()
    now_time = now_ist.time()
    current_time_str = now_time.strftime("%H:%M")
    day_name = now_ist.strftime("%A").upper() # MONDAY, etc.

    # 1. Exclude Weekends
    if now_ist.weekday() in [5, 6]:
        return

    # 2. Exclude Holidays
    if today in INDIAN_HOLIDAYS_2026:
        logger.debug(f"Holiday today: {today}. Skipping execution.")
        return

    # 3. Exclude times outside market hours (09:15 to 15:30 IST)
    market_open = time(9, 15)
    market_close = time(15, 30)
    if now_time < market_open or now_time > market_close:
        return

    logger.info(f"Scheduler executing parallel check at {current_time_str} IST")

    async with AsyncSessionLocal() as db:
        # Fetch only strategy IDs to keep the main session short
        stmt = select(Strategy.id).where(
            Strategy.status == "ACTIVE_LIVE",
            Strategy.is_active == True
        )
        res = await db.execute(stmt)
        active_ids = list(res.scalars().all())

    if active_ids:
        # Run all strategy evaluations concurrently in their own isolated connection sessions
        tasks = [process_strategy_entry(sid, today, current_time_str, day_name) for sid in active_ids]
        await asyncio.gather(*tasks)

async def check_and_execute_live_exits() -> None:
    """Evaluates all RUNNING strategy executions against live market Target, Stop Loss, and EOD Cutoff."""
    from app.strategies.models import StrategyExecution
    from app.market_data.live_market_service import get_real_strategy_contract
    from datetime import datetime, timezone
    from decimal import Decimal

    async with AsyncSessionLocal() as db:
        try:
            stmt = select(StrategyExecution).where(StrategyExecution.status == "RUNNING")
            res = await db.execute(stmt)
            running_execs = list(res.scalars().all())

            for ex in running_execs:
                strat = await db.get(Strategy, ex.strategy_id)
                if not strat:
                    continue

                stmt_ver = select(StrategyVersion).where(StrategyVersion.id == ex.strategy_version_id)
                res_ver = await db.execute(stmt_ver)
                version = res_ver.scalar_one_or_none()
                underlying = version.underlying if version else "NIFTY 50"

                spec = await get_real_strategy_contract(underlying, strat.name, strat.id)
                current_pnl = float(spec["pnl"])

                # Target (+₹500) and Stop Loss (-₹300) thresholds
                exit_matched = False
                exit_reason = ""
                if current_pnl >= 500.0:
                    exit_matched = True
                    exit_reason = f"🎯 TARGET PROFIT HIT: +₹{current_pnl:.2f} ({spec['symbol']} @ ₹{spec['currentLtp']})"
                elif current_pnl <= -300.0:
                    exit_matched = True
                    exit_reason = f"🛑 STOP LOSS HIT: -₹{abs(current_pnl):.2f} ({spec['symbol']} @ ₹{spec['currentLtp']})"

                if exit_matched:
                    now_utc = datetime.now(timezone.utc)
                    ex.status = "SQUARED_OFF"
                    ex.exit_time = now_utc
                    ex.realized_pnl = spec["pnl"]
                    ex.unrealized_pnl = Decimal("0.00")
                    ex.execution_logs = (ex.execution_logs or "") + f" | Auto Exit: {exit_reason}"
                    db.add(ex)
                    strat.status = "SQUARED_OFF"
                    db.add(strat)
                    logger.info(f"Live exit executed for Strategy #{strat.id}: {exit_reason}")

            await db.commit()
        except Exception as ex:
            logger.error(f"Error in check_and_execute_live_exits: {str(ex)}")

async def run_scheduler():
    scheduler = AsyncIOScheduler(timezone=ZONE_KOLKATA)
    scheduler.add_job(check_and_trigger_strategies, "cron", second="0")
    scheduler.add_job(check_and_execute_live_exits, "interval", seconds=15)
    scheduler.start()
    logger.info("Apscheduler triggered successfully with entry cron and 15s live exit interval (Asia/Kolkata)")
    
    # Keep the async loop running
    while True:
        await asyncio.sleep(3600)

def start_scheduler():
    try:
        asyncio.run(run_scheduler())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler worker stopped.")

if __name__ == "__main__":
    start_scheduler()

