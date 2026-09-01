import logging
from typing import Optional
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from app.market_data.schemas import MarketEvent
from app.execution.models import StrategySignal
from app.strategies.routing.schemas import StrategyRoute
from app.strategies.routing.enums import RouteType
from app.strategies.engine.schemas import StrategyEvaluationResult
from app.strategies.golden_rules.schemas import GoldenRulesGateResult
from app.strategies.golden_rules.enums import GateDecision
from app.strategies.signals.enums import SignalType, SignalDirection, SignalStatus
from app.strategies.signals.schemas import TradingSignal, build_deterministic_signal_key

logger = logging.getLogger(__name__)

class SignalEngine:
    """
    SignalEngine is responsible for converting verified strategy condition evaluations
    and mandatory Golden Rule gates into persistent, deterministic, and auditable TradingSignals.

    Architectural Boundary:
    - Does NOT evaluate conditions (owned by StrategyEngine)
    - Does NOT evaluate Golden Rules (owned by GoldenRuleEngine)
    - Does NOT evaluate user risk (owned by RiskEngine in Step 9)
    - Does NOT place broker orders (owned by ExecutionEngine in Step 10)
    """

    async def generate_signal(
        self,
        db: Optional[AsyncSession],
        route: StrategyRoute,
        event: MarketEvent,
        evaluation_result: StrategyEvaluationResult,
        golden_rule_result: Optional[GoldenRulesGateResult] = None,
        direction: SignalDirection = SignalDirection.BUY,
        persist: bool = True
    ) -> Optional[TradingSignal]:
        """
        Processes evaluation results and persists a StrategySignal if entry/exit criteria are fully satisfied.
        """
        # 1. Verify Strategy Condition Match
        if not evaluation_result.overall_matched:
            return None

        # 2. Gate Decision Validation
        if route.route_type == RouteType.ENTRY:
            if golden_rule_result is None or golden_rule_result.gate_decision != GateDecision.PASS:
                gate_decision_str = golden_rule_result.gate_decision.value if golden_rule_result else "MISSING"
                logger.info(
                    "signal_creation_blocked: strategy_id=%s version_id=%s event_id=%s gate_decision=%s reason=%s",
                    route.strategy_id,
                    route.strategy_version_id,
                    event.event_id,
                    gate_decision_str,
                    golden_rule_result.reason if golden_rule_result else "No Golden Rule result provided",
                    extra={
                        "event": "signal_creation_blocked",
                        "strategy_id": route.strategy_id,
                        "strategy_version_id": route.strategy_version_id,
                        "event_id": event.event_id,
                        "symbol": route.symbol,
                        "timeframe": route.timeframe,
                        "signal_type": route.route_type.value,
                        "gate_decision": gate_decision_str
                    }
                )
                return None
        # Note: RouteType.EXIT routes intentionally bypass Golden Rules (Safety Exit preservation)

        # 3. Derive Deterministic Identifiers
        signal_type_enum = SignalType.ENTRY if route.route_type == RouteType.ENTRY else SignalType.EXIT
        market_event_key = f"{route.strategy_id}:{route.symbol}:{route.timeframe}:{event.event_type.value}:{event.timestamp.isoformat()}"
        signal_key = build_deterministic_signal_key(
            strategy_id=route.strategy_id,
            strategy_version_id=route.strategy_version_id,
            signal_type=signal_type_enum,
            market_event_key=market_event_key
        )

        observed_price = event.price if event.price is not None else event.close

        # 4. Construct Explainability Reason
        matched_conds = sum(1 for c in evaluation_result.condition_results if c.matched)
        total_conds = len(evaluation_result.condition_results)
        gate_summary = (
            f"Gate PASS ({golden_rule_result.rules_passed}/{golden_rule_result.rules_evaluated} rules)"
            if golden_rule_result and golden_rule_result.gate_decision == GateDecision.PASS
            else "Safety Exit (Bypassed Golden Rules)"
        )
        reason = (
            f"{signal_type_enum.value}: Conditions MATCHED ({matched_conds}/{total_conds}). "
            f"{gate_summary}. Trigger Price: {observed_price}"
        )

        trading_signal = TradingSignal(
            signal_key=signal_key,
            strategy_id=route.strategy_id,
            strategy_version_id=route.strategy_version_id,
            market_event_key=market_event_key,
            event_id=event.event_id,
            symbol=route.symbol,
            timeframe=route.timeframe,
            signal_type=signal_type_enum,
            direction=direction,
            price=observed_price,
            status=SignalStatus.CREATED,
            reason=reason,
            created_at=datetime.now(timezone.utc)
        )

        # 5. Persist to Database if requested
        if persist and db is not None:
            trading_signal = await self._persist_signal(db, trading_signal, event)

        return trading_signal

    async def _persist_signal(
        self,
        db: AsyncSession,
        trading_signal: TradingSignal,
        event: MarketEvent
    ) -> TradingSignal:
        """
        Safely and atomically persists a StrategySignal inside a savepoint, protecting against concurrency races.
        """
        logger.info(
            "signal_creation_started: strategy_id=%s version_id=%s signal_key=%s",
            trading_signal.strategy_id,
            trading_signal.strategy_version_id,
            trading_signal.signal_key,
            extra={
                "event": "signal_creation_started",
                "strategy_id": trading_signal.strategy_id,
                "strategy_version_id": trading_signal.strategy_version_id,
                "market_event_key": trading_signal.market_event_key,
                "signal_key": trading_signal.signal_key,
                "signal_type": trading_signal.signal_type.value,
                "direction": trading_signal.direction.value,
                "symbol": trading_signal.symbol,
                "timeframe": trading_signal.timeframe
            }
        )

        trading_date = event.timestamp.date() if event.timestamp else date.today()
        entry_time_str = event.timestamp.strftime("%H:%M") if event.timestamp else "00:00"

        try:
            async with db.begin_nested():
                # Fast path idempotency check
                stmt = select(StrategySignal).where(StrategySignal.signal_key == trading_signal.signal_key)
                res = await db.execute(stmt)
                existing = res.scalar_one_or_none()

                if existing:
                    logger.info(
                        "signal_duplicate: strategy_id=%s version_id=%s signal_key=%s existing_signal_id=%s",
                        trading_signal.strategy_id,
                        trading_signal.strategy_version_id,
                        trading_signal.signal_key,
                        existing.id,
                        extra={
                            "event": "signal_duplicate",
                            "strategy_id": trading_signal.strategy_id,
                            "strategy_version_id": trading_signal.strategy_version_id,
                            "signal_key": trading_signal.signal_key,
                            "signal_id": existing.id,
                            "signal_type": trading_signal.signal_type.value
                        }
                    )
                    trading_signal.signal_id = existing.id
                    return trading_signal

                # Create StrategySignal row
                signal_model = StrategySignal(
                    strategy_id=trading_signal.strategy_id,
                    strategy_version_id=trading_signal.strategy_version_id,
                    trading_date=trading_date,
                    entry_time=entry_time_str,
                    signal_key=trading_signal.signal_key,
                    market_event_key=trading_signal.market_event_key,
                    signal_type=trading_signal.signal_type.value,
                    direction=trading_signal.direction.value,
                    status=trading_signal.status.value,
                    price=trading_signal.price,
                    reason=trading_signal.reason
                )
                db.add(signal_model)
                await db.flush()
                trading_signal.signal_id = signal_model.id

        except IntegrityError:
            # Concurrent worker inserted same signal_key simultaneously; savepoint safely rolled back
            logger.info(
                "signal_duplicate: strategy_id=%s version_id=%s signal_key=%s caught concurrent IntegrityError",
                trading_signal.strategy_id,
                trading_signal.strategy_version_id,
                trading_signal.signal_key,
                extra={
                    "event": "signal_duplicate",
                    "strategy_id": trading_signal.strategy_id,
                    "strategy_version_id": trading_signal.strategy_version_id,
                    "signal_key": trading_signal.signal_key,
                    "signal_type": trading_signal.signal_type.value
                }
            )
            # Retrieve existing record
            stmt = select(StrategySignal).where(StrategySignal.signal_key == trading_signal.signal_key)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                trading_signal.signal_id = existing.id
            return trading_signal

        except Exception as ex:
            logger.error(
                "signal_creation_failed: strategy_id=%s version_id=%s signal_key=%s error=%s",
                trading_signal.strategy_id,
                trading_signal.strategy_version_id,
                trading_signal.signal_key,
                str(ex),
                extra={
                    "event": "signal_creation_failed",
                    "strategy_id": trading_signal.strategy_id,
                    "strategy_version_id": trading_signal.strategy_version_id,
                    "market_event_key": trading_signal.market_event_key,
                    "signal_key": trading_signal.signal_key,
                    "signal_type": trading_signal.signal_type.value,
                    "error": str(ex)
                }
            )
            raise

        logger.info(
            "signal_created: signal_id=%s strategy_id=%s version_id=%s signal_type=%s direction=%s price=%s",
            trading_signal.signal_id,
            trading_signal.strategy_id,
            trading_signal.strategy_version_id,
            trading_signal.signal_type.value,
            trading_signal.direction.value,
            trading_signal.price,
            extra={
                "event": "signal_created",
                "strategy_id": trading_signal.strategy_id,
                "strategy_version_id": trading_signal.strategy_version_id,
                "market_event_key": trading_signal.market_event_key,
                "signal_key": trading_signal.signal_key,
                "signal_id": trading_signal.signal_id,
                "signal_type": trading_signal.signal_type.value,
                "direction": trading_signal.direction.value,
                "symbol": trading_signal.symbol,
                "timeframe": trading_signal.timeframe,
                "price": str(trading_signal.price) if trading_signal.price else None
            }
        )

        return trading_signal

signal_engine = SignalEngine()
