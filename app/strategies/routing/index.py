import asyncio
from typing import Dict, Set, List, Tuple, Optional
import logging
from app.strategies.enums import StrategyLifecycleState
from app.strategies.routing.schemas import CandidateStrategy
from app.strategies.routing.matcher import normalize_symbol_name

logger = logging.getLogger(__name__)

class StrategyRoutingIndex:
    """
    In-memory routing index for real-time, low-latency strategy candidate discovery.
    Maintains active strategies mapped by (symbol, timeframe) to eliminate database lookups on the tick path.
    """
    def __init__(self):
        # Key: strategy_id -> CandidateStrategy
        self._candidates: Dict[int, CandidateStrategy] = {}
        # Key: (normalized_symbol, normalized_timeframe) -> Set[strategy_id]
        self._index: Dict[Tuple[str, str], Set[int]] = {}
        self._lock = asyncio.Lock()

    async def register_candidate(self, candidate: CandidateStrategy) -> None:
        """Registers or updates a candidate strategy in the routing index."""
        async with self._lock:
            self._candidates[candidate.strategy_id] = candidate
            norm_sym = normalize_symbol_name(candidate.symbol)
            norm_tf = candidate.timeframe.strip().lower()
            key = (norm_sym, norm_tf)

            if key not in self._index:
                self._index[key] = set()
            self._index[key].add(candidate.strategy_id)

            logger.debug(
                f"Candidate strategy {candidate.strategy_id} registered in routing index for {key}",
                extra={
                    "event": "strategy_route_index_updated",
                    "strategy_id": candidate.strategy_id,
                    "symbol": candidate.symbol,
                    "timeframe": candidate.timeframe,
                    "lifecycle_state": candidate.lifecycle_state.value
                }
            )

    async def deregister_candidate(self, strategy_id: int) -> None:
        """Removes a strategy from the routing index."""
        async with self._lock:
            candidate = self._candidates.pop(strategy_id, None)
            if candidate:
                norm_sym = normalize_symbol_name(candidate.symbol)
                norm_tf = candidate.timeframe.strip().lower()
                key = (norm_sym, norm_tf)
                if key in self._index:
                    self._index[key].discard(strategy_id)
                    if not self._index[key]:
                        del self._index[key]

    async def update_candidate_state(self, strategy_id: int, new_state: StrategyLifecycleState) -> None:
        """Updates the runtime lifecycle state of an already-indexed candidate strategy."""
        async with self._lock:
            candidate = self._candidates.get(strategy_id)
            if candidate:
                candidate.lifecycle_state = new_state

    def get_candidates(self, symbol: str, timeframe: str) -> List[CandidateStrategy]:
        """
        Fast in-memory lookup of candidate strategies for a given symbol and timeframe.
        Returns matching candidates or all symbol candidates for fallback.
        """
        norm_sym = normalize_symbol_name(symbol)
        norm_tf = timeframe.strip().lower()
        key = (norm_sym, norm_tf)

        strategy_ids = self._index.get(key, set())
        matched = [self._candidates[sid] for sid in strategy_ids if sid in self._candidates]
        
        # If no exact match (e.g. event is TICK), also check general symbol subscribers
        if not matched:
            for (idx_sym, idx_tf), sids in self._index.items():
                if idx_sym == norm_sym:
                    for sid in sids:
                        if sid in self._candidates and self._candidates[sid] not in matched:
                            matched.append(self._candidates[sid])

        return matched

    def get_all_candidates(self) -> List[CandidateStrategy]:
        """Returns all registered candidate strategies."""
        return list(self._candidates.values())

    def clear(self) -> None:
        """Clears all indexed strategies (useful for test resets)."""
        self._candidates.clear()
        self._index.clear()
