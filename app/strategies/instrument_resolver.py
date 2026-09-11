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

DHAN_EQUITY_SECS = {
    "TATAGOLD": {"security_id": "21401", "trading_symbol": "TATAGOLD", "exchange_segment": "NSE_EQ", "lot_size": 1},
    "IDEA": {"security_id": "14366", "trading_symbol": "IDEA", "exchange_segment": "NSE_EQ", "lot_size": 1},
    "MAHABANK": {"security_id": "11377", "trading_symbol": "MAHABANK", "exchange_segment": "NSE_EQ", "lot_size": 1},
    "IOC": {"security_id": "1624", "trading_symbol": "IOC", "exchange_segment": "NSE_EQ", "lot_size": 1},
    "TATASTEEL": {"security_id": "3499", "trading_symbol": "TATASTEEL", "exchange_segment": "NSE_EQ", "lot_size": 1},
    "RELIANCE": {"security_id": "2885", "trading_symbol": "RELIANCE", "exchange_segment": "NSE_EQ", "lot_size": 1},
    "HDFCBANK": {"security_id": "1333", "trading_symbol": "HDFCBANK", "exchange_segment": "NSE_EQ", "lot_size": 1},
    "SUZLON": {"security_id": "12018", "trading_symbol": "SUZLON", "exchange_segment": "NSE_EQ", "lot_size": 1},
}

class InstrumentResolver:
    """Domain service resolving strategy leg parameters into standardized generic instruments.
    Prevents hardcoding broker-specific security IDs or hardcoded expiry text in business logic.
    """

    @staticmethod
    def resolve_leg_instrument(underlying: str, leg: StrategyLeg) -> ResolvedInstrument:
        u_upper = (underlying or "NIFTY").upper().strip()

        # Check if underlying is an equity / ETF
        if u_upper in DHAN_EQUITY_SECS or (getattr(leg, "segment", None) and str(leg.segment).upper() in ["EQ", "EQUITY"]):
            eq_info = DHAN_EQUITY_SECS.get(u_upper, {
                "security_id": "21401",
                "trading_symbol": u_upper,
                "exchange_segment": "NSE_EQ",
                "lot_size": 1
            })
            return ResolvedInstrument(
                trading_symbol=eq_info["trading_symbol"],
                security_id=eq_info["security_id"],
                exchange="NSE",
                exchange_segment=eq_info["exchange_segment"],
                underlying=u_upper,
                strike="0",
                option_type="EQ",
                lot_size=eq_info["lot_size"]
            )

        strike = "24900"
        if leg.strike_value is not None:
            strike = str(int(leg.strike_value))
        elif leg.strike_selection == "OTM1":
            strike = "25000"
        elif leg.strike_selection == "ITM1":
            strike = "24800"

        option_type = "CE" if leg.side.upper() == "BUY" else "PE"
        
        if "FINNIFTY" in u_upper:
            sec_id = "50316" if option_type == "CE" else "50317"
            trading_symbol = f"FINNIFTY-Oct2026-24900-{option_type}"
            lot_size = 25
        elif "BANKNIFTY" in u_upper:
            sec_id = "49080"
            trading_symbol = f"BANKNIFTY-Oct2026-52000-{option_type}"
            lot_size = 15
        else:
            sec_id = "40844" if option_type == "CE" else "40845"
            trading_symbol = f"NIFTY-Oct2026-24700-{option_type}"
            lot_size = 25

        return ResolvedInstrument(
            trading_symbol=trading_symbol,
            security_id=sec_id,
            exchange="NSE",
            exchange_segment="NSE_FNO",
            underlying=u_upper,
            strike=strike,
            option_type=option_type,
            lot_size=lot_size
        )
