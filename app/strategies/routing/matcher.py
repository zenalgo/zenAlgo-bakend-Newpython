from typing import Optional
from app.strategies.enums import StrategyLifecycleState
from app.strategies.routing.enums import RouteType

def normalize_symbol_name(symbol: str) -> str:
    """Normalizes symbol string (e.g. 'NIFTY 50' -> 'NIFTY', 'BANK NIFTY' -> 'BANKNIFTY')."""
    if not symbol:
        return ""
    cleaned = symbol.strip().upper()
    if cleaned in ("NIFTY 50", "NIFTY-50", "NIFTY50", "NIFTY"):
        return "NIFTY"
    if cleaned in ("BANK NIFTY", "BANKNIFTY", "NIFTY BANK"):
        return "BANKNIFTY"
    if cleaned in ("FIN NIFTY", "FINNIFTY", "NIFTY FIN SERVICE"):
        return "FINNIFTY"
    return cleaned.replace(" ", "")

def match_instrument(
    strategy_symbol: str,
    event_symbol: str,
    strategy_security_id: Optional[str] = None,
    event_security_id: Optional[str] = None
) -> bool:
    """Determines whether a strategy's target instrument matches the incoming market event."""
    if strategy_security_id and event_security_id:
        if str(strategy_security_id).strip() == str(event_security_id).strip():
            return True
        # If security IDs differ, check symbols as secondary confirmation
    
    norm_strat = normalize_symbol_name(strategy_symbol)
    norm_event = normalize_symbol_name(event_symbol)
    return bool(norm_strat and norm_strat == norm_event)

def match_timeframe(strategy_timeframe: str, event_timeframe: str) -> bool:
    """Determines whether a strategy's configured timeframe matches the market event timeframe."""
    if not strategy_timeframe or not event_timeframe:
        return False
    
    strat_tf = str(strategy_timeframe).strip().lower()
    event_tf = str(event_timeframe).strip().lower()

    if event_tf == "tick":
        # Ticks match tick-level evaluation or can be routed to all monitoring
        return strat_tf in ("tick", "1s", "realtime")

    return strat_tf == event_tf

def match_lifecycle_state(state: StrategyLifecycleState) -> Optional[RouteType]:
    """Determines whether a strategy is actively monitoring for entry or exit."""
    if state == StrategyLifecycleState.MONITORING_ENTRY:
        return RouteType.ENTRY
    elif state == StrategyLifecycleState.MONITORING_EXIT:
        return RouteType.EXIT
    return None
