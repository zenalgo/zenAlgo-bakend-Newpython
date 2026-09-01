import asyncio
import logging
from typing import List, Callable, Awaitable, Optional, Dict, Any

from app.market_data.schemas import MarketEvent
from app.strategies.enums import StrategyLifecycleState
from app.strategies.routing.enums import RouteType, RouteSkipReason
from app.strategies.routing.schemas import StrategyRoute, RouteSkip, RoutingDecisionResult, CandidateStrategy
from app.strategies.routing.index import StrategyRoutingIndex
from app.strategies.routing.matcher import match_instrument, match_timeframe, match_lifecycle_state

logger = logging.getLogger(__name__)

# Handler type for downstream Strategy Engine (Step 6)
RouteHandlerType = Callable[[StrategyRoute, MarketEvent], Awaitable[None]]

class StrategyRouter:
    """
    Market Event Routing Engine.
    Evaluates incoming canonical MarketEvents against active strategies and dispatches 
    structured StrategyRoutes asynchronously to downstream strategy engines.
    """
    def __init__(self, index: Optional[StrategyRoutingIndex] = None):
        self.index = index or StrategyRoutingIndex()
        self._handlers: List[RouteHandlerType] = []
        self._lock = asyncio.Lock()

    def add_handler(self, handler: RouteHandlerType) -> None:
        """Registers a downstream route handler (e.g. Strategy Engine)."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    def remove_handler(self, handler: RouteHandlerType) -> None:
        """Unregisters a route handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def _dispatch_route(self, route: StrategyRoute, event: MarketEvent) -> None:
        """Dispatches a StrategyRoute to all registered downstream handlers with error isolation."""
        for handler in self._handlers:
            try:
                res = handler(route, event)
                if asyncio.iscoroutine(res):
                    await res
                logger.debug(
                    f"Market event dispatched to strategy {route.strategy_id}: route_type={route.route_type.value}",
                    extra={
                        "event": "strategy_event_dispatched",
                        "strategy_id": route.strategy_id,
                        "strategy_version_id": route.strategy_version_id,
                        "event_id": route.event_id,
                        "symbol": route.symbol,
                        "timeframe": route.timeframe,
                        "route_type": route.route_type.value,
                        "lifecycle_state": route.lifecycle_state.value
                    }
                )
            except Exception as e:
                logger.error(
                    f"Error in route handler for strategy {route.strategy_id}: {str(e)}",
                    extra={
                        "event": "strategy_route_dispatch_failed",
                        "strategy_id": route.strategy_id,
                        "strategy_version_id": route.strategy_version_id,
                        "event_id": route.event_id,
                        "error": str(e)
                    }
                )

    async def route_market_event(self, event: MarketEvent) -> RoutingDecisionResult:
        """
        Main routing entry point:
        1. Queries in-memory RoutingIndex for candidates matching (symbol, timeframe).
        2. Evaluates lifecycle state, instrument identity, and timeframe.
        3. Constructs structured StrategyRoute objects for matching strategies.
        4. Dispatches routes asynchronously with failure isolation.
        """
        event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)

        logger.debug(
            f"Strategy router received market event: symbol={event.symbol}, timeframe={event.timeframe}, type={event_type_str}",
            extra={
                "event": "strategy_event_received_by_router",
                "event_id": event.event_id,
                "symbol": event.symbol,
                "security_id": event.security_id,
                "timeframe": event.timeframe,
                "event_type": event_type_str
            }
        )

        matched_routes: List[StrategyRoute] = []
        skipped_routes: List[RouteSkip] = []

        # 1. Retrieve candidates from in-memory index
        candidates = self.index.get_candidates(event.symbol, event.timeframe)

        for candidate in candidates:
            # A. Active Flag Check
            if not candidate.is_active:
                skipped_routes.append(RouteSkip(strategy_id=candidate.strategy_id, reason=RouteSkipReason.INACTIVE_STRATEGY))
                continue

            # B. Lifecycle State Check (Only MONITORING_ENTRY and MONITORING_EXIT are routed)
            route_type = match_lifecycle_state(candidate.lifecycle_state)
            if not route_type:
                reason = (
                    RouteSkipReason.INVALID_RUNTIME_STATE 
                    if candidate.lifecycle_state in (StrategyLifecycleState.ERROR, StrategyLifecycleState.RECONCILIATION_REQUIRED)
                    else RouteSkipReason.NOT_MONITORING
                )
                skipped_routes.append(RouteSkip(
                    strategy_id=candidate.strategy_id,
                    reason=reason,
                    details=f"Current lifecycle state: {candidate.lifecycle_state.value}"
                ))
                logger.debug(
                    f"Strategy {candidate.strategy_id} skipped: not monitoring (state={candidate.lifecycle_state.value})",
                    extra={
                        "event": "strategy_route_skip",
                        "strategy_id": candidate.strategy_id,
                        "event_id": event.event_id,
                        "reason": reason.value,
                        "lifecycle_state": candidate.lifecycle_state.value
                    }
                )
                continue

            # C. Instrument Matching Check
            if not match_instrument(candidate.symbol, event.symbol, candidate.security_id, event.security_id):
                skipped_routes.append(RouteSkip(
                    strategy_id=candidate.strategy_id,
                    reason=RouteSkipReason.SYMBOL_MISMATCH,
                    details=f"Strategy requires '{candidate.symbol}', event has '{event.symbol}'"
                ))
                logger.debug(
                    f"Strategy {candidate.strategy_id} skipped: symbol mismatch",
                    extra={
                        "event": "strategy_route_skip",
                        "strategy_id": candidate.strategy_id,
                        "event_id": event.event_id,
                        "reason": RouteSkipReason.SYMBOL_MISMATCH.value,
                        "required_symbol": candidate.symbol,
                        "event_symbol": event.symbol
                    }
                )
                continue

            # D. Timeframe Matching Check
            if not match_timeframe(candidate.timeframe, event.timeframe):
                skipped_routes.append(RouteSkip(
                    strategy_id=candidate.strategy_id,
                    reason=RouteSkipReason.TIMEFRAME_MISMATCH,
                    details=f"Strategy timeframe '{candidate.timeframe}' != event timeframe '{event.timeframe}'"
                ))
                logger.debug(
                    f"Strategy {candidate.strategy_id} skipped: timeframe mismatch",
                    extra={
                        "event": "strategy_route_skip",
                        "strategy_id": candidate.strategy_id,
                        "event_id": event.event_id,
                        "reason": RouteSkipReason.TIMEFRAME_MISMATCH.value,
                        "required_timeframe": candidate.timeframe,
                        "event_timeframe": event.timeframe
                    }
                )
                continue

            # E. All Matches Pass -> Construct Canonical Route
            route = StrategyRoute(
                strategy_id=candidate.strategy_id,
                strategy_version_id=candidate.strategy_version_id,
                lifecycle_state=candidate.lifecycle_state,
                event_id=event.event_id,
                route_type=route_type,
                symbol=event.symbol,
                timeframe=event.timeframe,
                event_type=event.event_type,
                timestamp=event.timestamp
            )
            matched_routes.append(route)

            logger.info(
                f"Strategy route match: strategy_id={route.strategy_id}, version_id={route.strategy_version_id}, route_type={route.route_type.value}",
                extra={
                    "event": "strategy_route_match",
                    "strategy_id": route.strategy_id,
                    "strategy_version_id": route.strategy_version_id,
                    "event_id": route.event_id,
                    "symbol": route.symbol,
                    "timeframe": route.timeframe,
                    "route_type": route.route_type.value,
                    "lifecycle_state": route.lifecycle_state.value
                }
            )

        # 2. Asynchronous Parallel Dispatch with Error Isolation
        if matched_routes:
            tasks = [self._dispatch_route(route, event) for route in matched_routes]
            await asyncio.gather(*tasks, return_exceptions=True)

        return RoutingDecisionResult(
            event_id=event.event_id,
            matched_routes=matched_routes,
            skipped_routes=skipped_routes
        )

# Global singleton router instance
strategy_router = StrategyRouter()
