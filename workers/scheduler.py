import asyncio
import logging
from datetime import datetime, date, time
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
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
from app.brokers.bootstrap import bootstrap_broker_adapters

# Ensure broker adapters are registered in the scheduler process
bootstrap_broker_adapters()

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
    from app.strategies.models import StrategyExecution, Strategy, StrategyVersion
    from app.market_data.live_market_service import get_real_strategy_contract
    from app.strategies.exit_calculator import extract_target_and_sl_config, calculate_exit_levels, validate_market_quote_freshness, is_eod_cutoff_reached
    from app.strategies.service import load_builder_fields
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

                stmt_ver = select(StrategyVersion).where(StrategyVersion.id == ex.strategy_version_id).options(
                    selectinload(StrategyVersion.exit_setting),
                    selectinload(StrategyVersion.legs)
                )
                res_ver = await db.execute(stmt_ver)
                version = res_ver.scalar_one_or_none()
                underlying = version.underlying if version else "NIFTY 50"

                spec = await get_real_strategy_contract(underlying, strat.name, strat.id)
                
                # Validate market quote freshness before evaluating exit decision
                is_fresh, val_msg = validate_market_quote_freshness(spec, expected_symbol=None, max_age_seconds=60.0)
                if not is_fresh:
                    logger.warning(f"Market quote invalid/stale for Strategy #{strat.id}: {val_msg}")
                    continue

                builder = load_builder_fields(strat)
                target_val, target_type, sl_val, sl_type = extract_target_and_sl_config(builder, version)

                real_entry = float(spec["entryPrice"])
                actual_qty = int(spec["lotSize"])
                current_ltp_f = float(spec["currentLtp"])

                levels = calculate_exit_levels(
                    entry_price=real_entry,
                    quantity=actual_qty,
                    current_ltp=current_ltp_f,
                    target_val=target_val,
                    target_type=target_type,
                    sl_val=sl_val,
                    sl_type=sl_type,
                    direction="BUY"
                )

                is_eod_met = is_eod_cutoff_reached("15:15")

                exit_matched = False
                exit_reason = ""
                if levels.is_target_met:
                    exit_matched = True
                    exit_reason = f"🎯 TARGET PROFIT ACHIEVED: +₹{levels.current_pnl:.2f} (LTP ₹{current_ltp_f:.2f} >= Target ₹{levels.target_price:.2f} on {spec['symbol']})"
                elif levels.is_sl_met:
                    exit_matched = True
                    exit_reason = f"🛑 STOP LOSS HIT: ₹{levels.current_pnl:.2f} (LTP ₹{current_ltp_f:.2f} <= SL ₹{levels.stop_loss_price:.2f} on {spec['symbol']})"
                elif is_eod_met:
                    exit_matched = True
                    exit_reason = f"⏰ 15:15 IST MANDATORY EOD SQUARE-OFF: PnL ₹{levels.current_pnl:.2f} ({spec['symbol']} @ ₹{current_ltp_f:.2f})"

                if exit_matched:
                    now_utc = datetime.now(timezone.utc)
                    ex.status = "SQUARED_OFF"
                    ex.exit_time = now_utc
                    ex.realized_pnl = Decimal(str(levels.current_pnl))
                    ex.unrealized_pnl = Decimal("0.00")
                    ex.execution_logs = (ex.execution_logs or "") + f" | Auto Exit: {exit_reason}"
                    db.add(ex)
                    strat.status = "SQUARED_OFF"
                    db.add(strat)
                    logger.info(f"Live exit executed for Strategy #{strat.id}: {exit_reason}")

            await db.commit()
        except Exception as ex:
            logger.error(f"Error in check_and_execute_live_exits: {str(ex)}")

async def sync_and_scan_market_strategies() -> None:
    """
    Automated Platform-Wide Market Scanner:
    1. Discovers all active strategies across all asset underlyings.
    2. Spawns and maintains LiveIndicatorEngines calculating real-time indicators for each asset symbol.
    3. Evaluates strategy conditions against fresh market data and indicators.
    4. Automatically emits signals and triggers live order execution.
    """
    from app.calculation_engine.registry import CalcEngineRegistry
    from app.calculation_engine.engine import LiveIndicatorEngine
    from app.calculation_engine.router import resolve_dhan_credentials_and_sec_id
    from app.strategies.instrument_resolver import DHAN_EQUITY_SECS

    async with AsyncSessionLocal() as db:
        try:
            stmt = (
                select(Strategy, StrategyVersion.underlying)
                .join(StrategyVersion, Strategy.current_version_id == StrategyVersion.id)
                .where(
                    Strategy.is_active == True,
                    Strategy.status.in_(["ACTIVE_LIVE", "ACTIVE_PAPER", "ACTIVE", "LIVE", "PAPER"])
                )
            )
            res = await db.execute(stmt)
            active_pairs = res.all()

            unique_symbols = set()
            for strat, underlying in active_pairs:
                clean_sym = (underlying or "NIFTY").upper().strip()
                if "NIFTY 50" in clean_sym or clean_sym == "NIFTY":
                    clean_sym = "NIFTY"
                elif "BANK" in clean_sym:
                    clean_sym = "BANKNIFTY"
                elif "FIN" in clean_sym:
                    clean_sym = "FINNIFTY"
                unique_symbols.add(clean_sym)

            for sym in unique_symbols:
                engine = CalcEngineRegistry.get(sym)
                if not engine or not getattr(engine, "is_running", False):
                    creds, sec_id, exch = await resolve_dhan_credentials_and_sec_id(db, sym)
                    if not sec_id:
                        if sym in DHAN_EQUITY_SECS:
                            sec_id = DHAN_EQUITY_SECS[sym]["security_id"]
                            exch = DHAN_EQUITY_SECS[sym]["exchange_segment"]
                        elif sym == "NIFTY":
                            sec_id = "13"
                            exch = "IDX_I"
                        elif sym == "BANKNIFTY":
                            sec_id = "25"
                            exch = "IDX_I"
                        elif sym == "FINNIFTY":
                            sec_id = "27"
                            exch = "IDX_I"

                    logger.info(f"Auto-spawning LiveIndicatorEngine for underlying: {sym} (sec_id: {sec_id})")
                    engine = LiveIndicatorEngine(
                        symbol=sym,
                        timeframe="5m",
                        security_id=sec_id,
                        exchange=exch,
                        credentials=creds
                    )
                    await engine.start()

                # Trigger condition evaluation against the fresh snapshot
                if engine and engine.snapshot:
                    await engine._evaluate_and_dispatch_conditions(trigger_type="SCAN")

        except Exception as e:
            logger.error(f"Error in sync_and_scan_market_strategies: {e}")

async def run_scheduler():
    scheduler = AsyncIOScheduler(timezone=ZONE_KOLKATA)
    scheduler.add_job(check_and_trigger_strategies, "cron", second="0")
    scheduler.add_job(check_and_execute_live_exits, "interval", seconds=15)
    scheduler.add_job(sync_and_scan_market_strategies, "interval", seconds=10)
    scheduler.start()
    logger.info("Apscheduler triggered successfully with entry cron, 15s exit interval, and 10s automated market scanner (Asia/Kolkata)")
    
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

