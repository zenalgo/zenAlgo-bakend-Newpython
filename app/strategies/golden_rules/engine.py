import logging
from typing import Optional, List, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.market_data.schemas import MarketEvent
from app.strategies.routing.schemas import StrategyRoute
from app.strategies.routing.enums import RouteType
from app.strategies.models import StrategyGoldenRule
from app.strategies.rules.rule_schema import ParsedRule
from app.strategies.engine.context import MarketContext
from app.strategies.golden_rules.enums import GoldenRuleStatus, GateDecision
from app.strategies.golden_rules.schemas import GoldenRuleEvaluationResult, GoldenRulesGateResult
from app.strategies.golden_rules.evaluator import evaluate_single_golden_rule

logger = logging.getLogger(__name__)

class GoldenRuleEngine:
    """
    Mandatory Trading Gate Engine.
    Evaluates mandatory Golden Rules following successful entry condition checks.
    Blocks signals if any mandatory gate constraint fails or if required market data is unavailable.
    """
    async def evaluate_golden_rules(
        self,
        db: Optional[AsyncSession],
        route: StrategyRoute,
        event: MarketEvent,
        context: MarketContext,
        explicit_rules: Optional[List[Union[StrategyGoldenRule, ParsedRule]]] = None
    ) -> GoldenRulesGateResult:
        """
        Main gate evaluation entrypoint:
        1. Bypasses check for EXIT routes to guarantee safety exits.
        2. Retrieves Golden Rules for the active StrategyVersion.
        3. Evaluates each mandatory constraint.
        4. Fails closed (BLOCKED) if any rule fails or data is missing.
        5. Emits structured observability logs.
        """
        # Safety Exit Check: Golden Rules are entry gates only
        if route.route_type == RouteType.EXIT:
            return GoldenRulesGateResult(
                strategy_id=route.strategy_id,
                strategy_version_id=route.strategy_version_id,
                event_id=event.event_id,
                gate_decision=GateDecision.PASS,
                all_passed=True,
                rules_evaluated=0,
                rules_passed=0,
                rules_failed=0,
                rules_unavailable=0,
                rule_results=[],
                reason="Golden Rules not applied to safety EXIT routes"
            )

        # 1. Retrieve Golden Rules for active StrategyVersion
        rules_to_eval: List[Union[StrategyGoldenRule, ParsedRule]] = []
        if explicit_rules:
            rules_to_eval.extend(explicit_rules)
        elif db is not None:
            stmt = select(StrategyGoldenRule).where(
                StrategyGoldenRule.strategy_version_id == route.strategy_version_id
            )
            res = await db.execute(stmt)
            rules_to_eval = list(res.scalars().all())

        if not rules_to_eval:
            return GoldenRulesGateResult(
                strategy_id=route.strategy_id,
                strategy_version_id=route.strategy_version_id,
                event_id=event.event_id,
                gate_decision=GateDecision.PASS,
                all_passed=True,
                rules_evaluated=0,
                rules_passed=0,
                rules_failed=0,
                rules_unavailable=0,
                rule_results=[],
                reason="No Golden Rules configured for strategy version"
            )

        logger.info(
            f"Golden Rule evaluation started for strategy {route.strategy_id} ({len(rules_to_eval)} rule(s))",
            extra={
                "event": "golden_rule_evaluation_started",
                "strategy_id": route.strategy_id,
                "strategy_version_id": route.strategy_version_id,
                "event_id": event.event_id,
                "rule_count": len(rules_to_eval)
            }
        )

        # 2. Evaluate Each Mandatory Rule
        rule_results: List[GoldenRuleEvaluationResult] = []
        passed_count = 0
        failed_count = 0
        unavail_count = 0

        for r in rules_to_eval:
            eval_res = evaluate_single_golden_rule(r, context)
            rule_results.append(eval_res)

            if eval_res.status == GoldenRuleStatus.PASS:
                passed_count += 1
                logger.debug(
                    f"Golden rule PASSED: confirmation={eval_res.confirmation}, reason={eval_res.reason}",
                    extra={
                        "event": "golden_rule_passed",
                        "strategy_id": route.strategy_id,
                        "event_id": event.event_id,
                        "confirmation": eval_res.confirmation,
                        "observed_value": eval_res.observed_value,
                        "expected_value": eval_res.expected_value
                    }
                )
            elif eval_res.status == GoldenRuleStatus.DATA_UNAVAILABLE:
                unavail_count += 1
                logger.warning(
                    f"Golden rule DATA_UNAVAILABLE: confirmation={eval_res.confirmation}, reason={eval_res.reason}",
                    extra={
                        "event": "golden_rule_data_unavailable",
                        "strategy_id": route.strategy_id,
                        "event_id": event.event_id,
                        "confirmation": eval_res.confirmation,
                        "reason": eval_res.reason
                    }
                )
            else:
                failed_count += 1
                logger.info(
                    f"Golden rule FAILED: confirmation={eval_res.confirmation}, reason={eval_res.reason}",
                    extra={
                        "event": "golden_rule_failed",
                        "strategy_id": route.strategy_id,
                        "event_id": event.event_id,
                        "confirmation": eval_res.confirmation,
                        "observed_value": eval_res.observed_value,
                        "expected_value": eval_res.expected_value,
                        "reason": eval_res.reason
                    }
                )

        # 3. Aggregate Gate Decision (Mandatory Semantics: All must PASS)
        all_passed = (passed_count == len(rules_to_eval) and failed_count == 0 and unavail_count == 0)
        gate_decision = GateDecision.PASS if all_passed else GateDecision.BLOCKED
        reason = (
            "All mandatory Golden Rules satisfied" 
            if all_passed 
            else f"Mandatory gate blocked ({failed_count} failed, {unavail_count} data unavailable out of {len(rules_to_eval)})"
        )

        log_event = "golden_rule_gate_passed" if all_passed else "golden_rule_gate_blocked"
        logger.info(
            f"Golden Rule Gate {gate_decision.value} for strategy {route.strategy_id}: {reason}",
            extra={
                "event": log_event,
                "strategy_id": route.strategy_id,
                "strategy_version_id": route.strategy_version_id,
                "event_id": event.event_id,
                "gate_decision": gate_decision.value,
                "all_passed": all_passed,
                "rules_passed": passed_count,
                "rules_failed": failed_count,
                "rules_unavailable": unavail_count
            }
        )

        return GoldenRulesGateResult(
            strategy_id=route.strategy_id,
            strategy_version_id=route.strategy_version_id,
            event_id=event.event_id,
            gate_decision=gate_decision,
            all_passed=all_passed,
            rules_evaluated=len(rules_to_eval),
            rules_passed=passed_count,
            rules_failed=failed_count,
            rules_unavailable=unavail_count,
            rule_results=rule_results,
            reason=reason
        )

# Global singleton instance
golden_rule_engine = GoldenRuleEngine()
