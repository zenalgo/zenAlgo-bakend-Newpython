import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.market_data.schemas import MarketEvent
from app.strategies.routing.schemas import StrategyRoute
from app.strategies.routing.enums import RouteType
from app.strategies.models import StrategyVersion, StrategyCondition
from app.strategies.rules.rule_schema import ParsedRule
from app.strategies.parser.deterministic_parser import parse_logical_expression
from app.strategies.engine.enums import EvaluationStatus
from app.strategies.engine.schemas import ConditionEvaluationResult, StrategyEvaluationResult
from app.strategies.engine.context import MarketContext
from app.strategies.engine.indicator_provider import BaseIndicatorProvider, default_indicator_provider
from app.strategies.engine.condition_evaluator import evaluate_condition
from app.strategies.engine.idempotency import claim_strategy_event_processing

logger = logging.getLogger(__name__)

class StrategyEngine:
    """
    Core Condition Evaluation & Strategy Engine.
    Evaluates canonical MarketEvents against a strategy's active StrategyVersion rules,
    enforces event idempotency, and returns structured evaluation results.
    """
    def __init__(self, indicator_provider: Optional[BaseIndicatorProvider] = None):
        self.indicator_provider = indicator_provider or default_indicator_provider

    async def evaluate_strategy_route(
        self,
        db: Optional[AsyncSession],
        route: StrategyRoute,
        event: MarketEvent,
        context: Optional[MarketContext] = None,
        explicit_rules: Optional[List[ParsedRule]] = None
    ) -> StrategyEvaluationResult:
        """
        Main engine evaluation entrypoint:
        1. Checks and claims strategy event idempotency (if db session provided).
        2. Constructs/enriches MarketContext with price, candle, and indicators.
        3. Retrieves active StrategyVersion conditions matching RouteType (ENTRY or EXIT).
        4. Evaluates all conditions deterministically.
        5. Logs and returns structured StrategyEvaluationResult.
        """
        route_type_str = route.route_type.value if hasattr(route.route_type, "value") else str(route.route_type)
        market_event_key = f"{route.strategy_id}:{event.event_id}"

        # 1. Strategy-Level Event Idempotency Claim
        if db is not None:
            claimed = await claim_strategy_event_processing(db, route.strategy_id, market_event_key)
            if not claimed:
                logger.info(
                    f"Duplicate event evaluation skipped: strategy_id={route.strategy_id}, event_key={market_event_key}",
                    extra={
                        "event": "strategy_event_evaluation_skipped",
                        "strategy_id": route.strategy_id,
                        "market_event_key": market_event_key,
                        "reason": "DUPLICATE_EVENT_CLAIM"
                    }
                )
                return StrategyEvaluationResult(
                    strategy_id=route.strategy_id,
                    strategy_version_id=route.strategy_version_id,
                    event_id=event.event_id,
                    route_type=route_type_str,
                    status=EvaluationStatus.SKIPPED,
                    overall_matched=False
                )

        logger.info(
            f"Strategy evaluation started: strategy_id={route.strategy_id}, version_id={route.strategy_version_id}, route_type={route_type_str}",
            extra={
                "event": "strategy_evaluation_started",
                "strategy_id": route.strategy_id,
                "strategy_version_id": route.strategy_version_id,
                "event_id": event.event_id,
                "market_event_key": market_event_key,
                "route_type": route_type_str,
                "symbol": event.symbol,
                "timeframe": event.timeframe
            }
        )

        # 2. Build / Enrich MarketContext
        if context is None:
            indicators = self.indicator_provider.get_indicator_context(event.symbol, event.timeframe)
            context = MarketContext(
                symbol=event.symbol,
                timestamp=event.timestamp,
                timeframe=event.timeframe,
                current_price=event.price or event.close,
                candle=event,
                indicators=indicators
            )

        # 3. Retrieve Conditions to Evaluate
        parsed_rules: List[ParsedRule] = []

        if explicit_rules:
            parsed_rules.extend(explicit_rules)
        elif db is not None:
            # Query conditions from StrategyVersion
            stmt = select(StrategyCondition).where(
                StrategyCondition.strategy_version_id == route.strategy_version_id,
                StrategyCondition.rule_type == route_type_str
            )
            res = await db.execute(stmt)
            cond_records = res.scalars().all()

            for rec in cond_records:
                if rec.rule_json:
                    try:
                        rule_dict = json.loads(rec.rule_json)
                        parsed_rules.append(ParsedRule.model_validate(rule_dict))
                    except Exception:
                        parsed = parse_logical_expression(rec.raw_text, default_timeframe=event.timeframe)
                        if parsed:
                            parsed_rules.append(parsed)
                elif rec.raw_text:
                    parsed = parse_logical_expression(rec.raw_text, default_timeframe=event.timeframe)
                    if parsed:
                        parsed_rules.append(parsed)

        # 4. Evaluate Conditions
        condition_results: List[ConditionEvaluationResult] = []

        for p_rule in parsed_rules:
            cond_res = evaluate_condition(p_rule, context)
            condition_results.append(cond_res)

            log_event = "condition_matched" if cond_res.matched else "condition_not_matched"
            logger.debug(
                f"Condition evaluated: rule_type={cond_res.rule_type}, matched={cond_res.matched}, reason={cond_res.reason}",
                extra={
                    "event": log_event,
                    "strategy_id": route.strategy_id,
                    "event_id": event.event_id,
                    "rule_type": cond_res.rule_type,
                    "matched": cond_res.matched,
                    "current_value": cond_res.current_value,
                    "previous_value": cond_res.previous_value,
                    "threshold": cond_res.threshold,
                    "reason": cond_res.reason
                }
            )

        # 5. Determine Overall Match
        if not condition_results:
            overall_matched = False
            status = EvaluationStatus.NOT_MATCHED
        elif any(cr.status == EvaluationStatus.DATA_UNAVAILABLE for cr in condition_results):
            overall_matched = False
            status = EvaluationStatus.DATA_UNAVAILABLE
        elif all(cr.matched for cr in condition_results):
            overall_matched = True
            status = EvaluationStatus.MATCHED
        else:
            overall_matched = False
            status = EvaluationStatus.NOT_MATCHED

        result = StrategyEvaluationResult(
            strategy_id=route.strategy_id,
            strategy_version_id=route.strategy_version_id,
            event_id=event.event_id,
            route_type=route_type_str,
            status=status,
            overall_matched=overall_matched,
            condition_results=condition_results
        )

        logger.info(
            f"Strategy evaluation completed: strategy_id={route.strategy_id}, status={status.value}, overall_matched={overall_matched}",
            extra={
                "event": "strategy_evaluation_completed",
                "strategy_id": route.strategy_id,
                "strategy_version_id": route.strategy_version_id,
                "event_id": event.event_id,
                "status": status.value,
                "overall_matched": overall_matched
            }
        )

        return result

# Global singleton instance
strategy_engine = StrategyEngine()
