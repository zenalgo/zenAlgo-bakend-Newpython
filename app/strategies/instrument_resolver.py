from pydantic import BaseModel
from typing import Optional
from app.strategies.models import StrategyLeg

class ResolvedInstrument(BaseModel):
    trading_symbol: str
    security_id: Optional[str] = None
    exchange: str = "NSE"
    exchange_segment: str = "NSE_FN"
    underlying: str
    strike: str
    option_type: str
    lot_size: int = 50

class InstrumentResolver:
    """Domain service resolving strategy leg parameters into standardized generic instruments.
    Prevents hardcoding broker-specific security IDs or hardcoded expiry text in business logic.
    """

    @staticmethod
    def resolve_leg_instrument(underlying: str, leg: StrategyLeg) -> ResolvedInstrument:
        strike = "25000"
        if leg.strike_value is not None:
            strike = str(int(leg.strike_value))
        elif leg.strike_selection == "OTM1":
            strike = "25100"
        elif leg.strike_selection == "ITM1":
            strike = "24900"

        option_type = "CE" if leg.side.upper() == "BUY" else "PE"
        trading_symbol = f"{underlying}_{strike}_{option_type}"
        security_id = f"SEC_{underlying}_{strike}_{option_type}"
        lot_size = 50 if underlying.upper() == "NIFTY" else 15

        return ResolvedInstrument(
            trading_symbol=trading_symbol,
            security_id=security_id,
            exchange="NSE",
            exchange_segment="NSE_FN",
            underlying=underlying,
            strike=strike,
            option_type=option_type,
            lot_size=lot_size
        )
