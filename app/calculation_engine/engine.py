"""
Calculation Engine — Live Indicator Engine
Runs per symbol + timeframe.
Features:
  - Subscribes to MarketDataService for Dhan WebSocket ticks and candle close events
  - Computes real-time session VWAP and LTP instantly on every tick (~100-500ms)
  - Recalculates full technical indicators on every candle close
  - Evaluates strategy conditions (rule_json) and fires SignalEvents
  - 5-second polling fallback if WebSocket ticks are unavailable
  - Real-time WebSocket broadcasting to connected admin dashboards
"""
import asyncio
from collections import deque
from datetime import datetime, timezone, date
import logging
from typing import Dict, Any, List, Optional
import uuid

from app.calculation_engine.schemas import IndicatorSnapshot, IndicatorValue, SignalEvent
from app.calculation_engine.indicators import compute_all_indicators
from app.calculation_engine.data_fetcher import get_candles
from app.calculation_engine.condition_evaluator import (
    evaluate_conditions_against_snapshot,
    fetch_active_conditions_for_symbol,
)
from app.calculation_engine.registry import CalcEngineRegistry, CalcEngineWSManager
from app.market_data.enums import MarketEventType
from app.market_data.schemas import MarketEvent
from app.market_data.service import market_data_service
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class LiveIndicatorEngine:
    """
    Live real-time technical calculation engine instance for a specific asset symbol.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str = "5m",
        security_id: Optional[str] = None,
        exchange: str = "NSE_EQ",
        credentials: Optional[Dict[str, Any]] = None,
    ):
        self.symbol = symbol.strip().upper()
        self.timeframe = timeframe
        self.security_id = security_id
        self.exchange = exchange
        self.credentials = credentials

        self.is_running: bool = False
        self.started_at: Optional[datetime] = None
        self.last_snapshot_at: Optional[datetime] = None
        self.data_source: str = "DHAN"
        self.websocket_connected: bool = False
        self.fallback_polling: bool = False

        # In-memory rolling window of OHLCV candles
        self.candles: List[Dict[str, Any]] = []
        self.snapshot: Optional[IndicatorSnapshot] = None
        self.recent_signals: deque = deque(maxlen=50)

        # Session VWAP accumulators (price * volume sum)
        self.session_date: date = datetime.now(timezone.utc).date()
        self.cumulative_pv: float = 0.0
        self.cumulative_v: float = 0.0
        self.current_ltp: Optional[float] = None
        self.current_vwap: Optional[float] = None

        self._last_tick_time: Optional[datetime] = None
        self._fallback_task: Optional[asyncio.Task] = None
        self._strategy_last_signal_time: Dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the live engine: initial candle fetch, subscribe to feeds, start fallback."""
        if self.is_running:
            return

        self.is_running = True
        self.started_at = datetime.now(timezone.utc)
        logger.info(f"Starting LiveIndicatorEngine for {self.symbol} [{self.timeframe}]")

        # 1. Register in global registry
        CalcEngineRegistry.register(self.symbol, self)

        # 2. Fetch initial candle history (200 candles)
        try:
            initial_candles, source = await get_candles(
                symbol=self.symbol,
                timeframe=self.timeframe,
                security_id=self.security_id,
                exchange_segment=self.exchange,
                credentials=self.credentials,
            )
            self.candles = initial_candles[-200:]
            self.data_source = source
            self._init_session_vwap_from_candles()
            self._recalculate_snapshot()
        except Exception as e:
            logger.error(f"Error initializing candles for {self.symbol}: {e}")

        # 3. Subscribe to MarketDataService feed and add listener
        try:
            await market_data_service.subscribe([self.symbol])
            market_data_service.add_listener(self.on_market_event)
            self.websocket_connected = True
        except Exception as e:
            logger.warning(f"Could not hook into MarketDataService for {self.symbol}: {e}")

        # 4. Start 5-second polling fallback task
        self._fallback_task = asyncio.create_task(self._run_fallback_loop())

        # 5. Broadcast initial snapshot
        if self.snapshot:
            await self._broadcast_snapshot()

    async def stop(self) -> None:
        """Stop engine and clean up subscriptions and background tasks."""
        self.is_running = False
        logger.info(f"Stopping LiveIndicatorEngine for {self.symbol}")

        if self._fallback_task and not self._fallback_task.done():
            self._fallback_task.cancel()

        try:
            market_data_service.remove_listener(self.on_market_event)
            await market_data_service.unsubscribe([self.symbol])
        except Exception as e:
            logger.debug(f"Error unregistering market data listener: {e}")

        CalcEngineRegistry.remove(self.symbol)

    def _init_session_vwap_from_candles(self) -> None:
        """Calculate running session VWAP from intraday candles."""
        today = datetime.now(timezone.utc).date()
        self.session_date = today
        self.cumulative_pv = 0.0
        self.cumulative_v = 0.0

        for c in self.candles:
            c_ts = c.get("timestamp")
            if hasattr(c_ts, "date") and c_ts.date() == today:
                typical_price = (c["high"] + c["low"] + c["close"]) / 3.0
                vol = float(c.get("volume", 0.0) or 0.0)
                if vol > 0:
                    self.cumulative_pv += typical_price * vol
                    self.cumulative_v += vol

        if self.cumulative_v > 0:
            self.current_vwap = round(self.cumulative_pv / self.cumulative_v, 2)
        elif self.candles:
            self.current_vwap = round(self.candles[-1]["close"], 2)

        if self.candles:
            self.current_ltp = round(self.candles[-1]["close"], 2)

    def _recalculate_snapshot(self) -> None:
        """Recalculate full indicators from current candles array."""
        if not self.candles:
            return

        snap_dict = compute_all_indicators(
            candles=self.candles,
            symbol=self.symbol,
            timeframe=self.timeframe,
            ltp=self.current_ltp,
            vwap=self.current_vwap,
            data_source=self.data_source,
        )

        ind_objects: List[IndicatorValue] = []
        for raw_ind in snap_dict.get("indicators", []):
            ind_objects.append(IndicatorValue(**raw_ind))

        self.snapshot = IndicatorSnapshot(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=datetime.now(timezone.utc),
            ltp=self.current_ltp or snap_dict.get("ltp"),
            vwap=self.current_vwap or snap_dict.get("vwap"),
            indicators=ind_objects,
            candle_count=snap_dict.get("candle_count", len(self.candles)),
            is_market_hours=snap_dict.get("is_market_hours", True),
            data_source=self.data_source,
        )
        self.last_snapshot_at = self.snapshot.timestamp

    async def on_market_event(self, event: MarketEvent) -> None:
        """
        MarketDataService event listener callback.
        Handles real-time TICK events and CANDLE_CLOSED events.
        """
        if not self.is_running or event.symbol != self.symbol:
            return

        now = datetime.now(timezone.utc)
        self._last_tick_time = now

        # 1. REAL-TIME TICK (~100-500ms)
        if event.event_type == MarketEventType.TICK:
            if event.price is not None:
                self.current_ltp = round(float(event.price), 2)

                # Reset VWAP if session changed to new day
                if now.date() != self.session_date:
                    self.session_date = now.date()
                    self.cumulative_pv = 0.0
                    self.cumulative_v = 0.0

                # Accumulate volume weighted price
                tick_vol = float(event.volume or 1.0)
                self.cumulative_pv += self.current_ltp * tick_vol
                self.cumulative_v += tick_vol
                if self.cumulative_v > 0:
                    self.current_vwap = round(self.cumulative_pv / self.cumulative_v, 2)

                # Update live snapshot values
                if self.snapshot:
                    self.snapshot.ltp = self.current_ltp
                    self.snapshot.vwap = self.current_vwap

                    # Update VWAP indicator item if present
                    for ind in self.snapshot.indicators:
                        if ind.name == "VWAP":
                            ind.value = self.current_vwap

                # Real-time condition evaluation for VWAP/price conditions
                await self._evaluate_and_dispatch_conditions(trigger_type="TICK")

                # Broadcast tick snapshot
                await self._broadcast_tick()

        # 2. CANDLE CLOSE EVENT
        elif event.event_type == MarketEventType.CANDLE_CLOSED:
            if event.close is not None:
                new_candle = {
                    "timestamp": event.timestamp,
                    "open": float(event.open or event.close),
                    "high": float(event.high or event.close),
                    "low": float(event.low or event.close),
                    "close": float(event.close),
                    "volume": float(event.volume or 0),
                }
                async with self._lock:
                    self.candles.append(new_candle)
                    if len(self.candles) > 200:
                        self.candles = self.candles[-200:]
                    self.current_ltp = new_candle["close"]
                    self._recalculate_snapshot()

                # Full condition evaluation across all indicators
                await self._evaluate_and_dispatch_conditions(trigger_type="CANDLE_CLOSE")
                await self._broadcast_snapshot()

    async def _evaluate_and_dispatch_conditions(self, trigger_type: str = "CANDLE_CLOSE") -> None:
        """Check active strategy conditions, emit database signals, and trigger order execution."""
        if not self.snapshot:
            return

        try:
            async with AsyncSessionLocal() as db:
                conditions = await fetch_active_conditions_for_symbol(db, self.symbol)
                if not conditions:
                    return

                signals = await evaluate_conditions_against_snapshot(
                    snapshot=self.snapshot,
                    conditions_with_strategy=conditions,
                    trigger_type=trigger_type,
                )

                now_ts = datetime.now(timezone.utc).timestamp()

                for sig in signals:
                    self.recent_signals.appendleft(sig)
                    logger.info(
                        f"🎯 SIGNAL FIRED: [{sig.signal}] {sig.symbol} {sig.condition_text} "
                        f"({sig.indicator_name}={sig.indicator_value}) -> Strategy {sig.strategy_name} (ID: {sig.strategy_id})"
                    )
                    # Broadcast signal event to WebSocket subscribers
                    await CalcEngineWSManager.broadcast({
                        "type": "SIGNAL_EVENT",
                        "data": sig.model_dump(mode="json"),
                    })

                    # Deduplication / cooldown check: 60s cooldown per strategy
                    last_sig_time = self._strategy_last_signal_time.get(sig.strategy_id, 0.0)
                    if now_ts - last_sig_time < 60.0:
                        continue

                    # Process ENTRY or EXIT
                    if sig.signal.upper() == "ENTRY":
                        from app.strategies.models import Strategy, StrategyExecution
                        from app.execution.models import StrategySignal
                        from app.execution import service as exec_service
                        import pytz
                        from decimal import Decimal
                        from sqlalchemy import select

                        res_strat = await db.execute(select(Strategy).where(Strategy.id == sig.strategy_id))
                        strat = res_strat.scalar_one_or_none()
                        if not strat or not strat.is_active or strat.status not in ("ACTIVE_LIVE", "ACTIVE_PAPER", "ACTIVE", "PAPER", "LIVE"):
                            continue

                        # Check if an execution is already RUNNING for this strategy
                        stmt_running = select(StrategyExecution).where(
                            StrategyExecution.strategy_id == sig.strategy_id,
                            StrategyExecution.status == "RUNNING"
                        )
                        res_running = await db.execute(stmt_running)
                        if res_running.scalar_one_or_none():
                            logger.info(f"Strategy {sig.strategy_id} already has a RUNNING execution. Skipping duplicate entry.")
                            continue

                        zone_kolkata = pytz.timezone("Asia/Kolkata")
                        now_ist = datetime.now(zone_kolkata)
                        today = now_ist.date()
                        entry_time = now_ist.strftime("%H:%M:%S")[:10]
                        sig_key = f"SIG-{sig.strategy_id}-{int(now_ts)}"

                        db_signal = StrategySignal(
                            strategy_id=sig.strategy_id,
                            strategy_version_id=strat.current_version_id,
                            trading_date=today,
                            entry_time=entry_time,
                            signal_key=sig_key,
                            signal_type="ENTRY",
                            direction="BUY",
                            status="CREATED",
                            price=Decimal(str(sig.indicator_value or self.current_ltp or 100.0)),
                            reason=sig.condition_text
                        )
                        db.add(db_signal)
                        await db.commit()
                        await db.refresh(db_signal)

                        self._strategy_last_signal_time[sig.strategy_id] = now_ts
                        logger.info(f"🚀 Spawning order execution batch for Signal ID {db_signal.id} on Strategy {sig.strategy_name}...")
                        asyncio.create_task(exec_service.execute_signal_batch(db_signal.id))

                    elif sig.signal.upper() == "EXIT":
                        from app.execution import service as exec_service
                        self._strategy_last_signal_time[sig.strategy_id] = now_ts
                        logger.info(f"🛑 Triggering square-off for Strategy {sig.strategy_name} on EXIT condition: {sig.condition_text}")
                        asyncio.create_task(exec_service.exit_all_positions(db, sig.strategy_id))

        except Exception as e:
            logger.debug(f"Condition evaluation loop error: {e}")

    async def _run_fallback_loop(self) -> None:
        """
        Fallback loop: polls REST/yfinance every 5s if WebSocket tick stream is absent.
        Guarantees that indicators stay fresh even if Dhan WebSocket is disconnected.
        """
        while self.is_running:
            try:
                await asyncio.sleep(5.0)

                # Check if recent tick occurred within the last 6 seconds
                now = datetime.now(timezone.utc)
                has_active_ticks = (
                    self._last_tick_time is not None
                    and (now - self._last_tick_time).total_seconds() < 6.0
                )

                if not has_active_ticks:
                    self.fallback_polling = True
                    candles, src = await get_candles(
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        security_id=self.security_id,
                        exchange_segment=self.exchange,
                        credentials=self.credentials,
                    )
                    if candles:
                        async with self._lock:
                            self.candles = candles[-200:]
                            self.data_source = src
                            if self.candles:
                                self.current_ltp = round(self.candles[-1]["close"], 2)
                            self._init_session_vwap_from_candles()
                            self._recalculate_snapshot()

                        await self._evaluate_and_dispatch_conditions(trigger_type="CANDLE_CLOSE")
                        await self._broadcast_snapshot()
                else:
                    self.fallback_polling = False

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in calculation engine fallback loop for {self.symbol}: {e}")

    async def _broadcast_snapshot(self) -> None:
        """Broadcast full indicator snapshot to connected clients."""
        if not self.snapshot:
            return
        msg = {
            "type": "INDICATOR_SNAPSHOT",
            "symbol": self.symbol,
            "data": self.snapshot.model_dump(mode="json"),
            "recent_signals": [s.model_dump(mode="json") for s in list(self.recent_signals)[:10]],
        }
        await CalcEngineWSManager.broadcast(msg)

    async def _broadcast_tick(self) -> None:
        """Broadcast fast lightweight tick price & VWAP."""
        msg = {
            "type": "TICK_UPDATE",
            "symbol": self.symbol,
            "ltp": self.current_ltp,
            "vwap": self.current_vwap,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await CalcEngineWSManager.broadcast(msg)

    def get_snapshot(self) -> Optional[IndicatorSnapshot]:
        return self.snapshot
