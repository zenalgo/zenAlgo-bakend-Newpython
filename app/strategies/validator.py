from typing import List, Set, Optional
from decimal import Decimal
import re
from app.strategies.schemas import StrategyRequest, StrategyValidationError, StrategyValidationResponse

SUPPORTED_UNDERLYINGS: Set[str] = {
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX",
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT"
}
SUPPORTED_TRADING_TYPES: Set[str] = {"INTRADAY", "DELIVERY"}
SUPPORTED_SEGMENTS: Set[str] = {"OPT", "EQ", "FUT"}
SUPPORTED_SIDES: Set[str] = {"BUY", "SELL"}
SUPPORTED_STRIKES: Set[str] = {"ATM", "OTM", "ITM", "OTM1", "OTM2", "OTM3", "ITM1", "ITM2", "ITM3", "CUSTOM"}
SUPPORTED_EXPIRIES: Set[str] = {"CURRENT", "NEXT", "WEEKLY", "MONTHLY", "CUSTOM"}
SUPPORTED_DAYS: Set[str] = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"}

def validate_target_stop_loss(value: Optional[Decimal], sl_type: str, path: str, errors: List[StrategyValidationError]) -> None:
    """Ensures stop loss or target parameters are strictly positive if type is not NONE."""
    if sl_type and sl_type.upper() != "NONE":
        if value is None or value <= Decimal("0.00"):
            errors.append(StrategyValidationError(
                field=f"{path}.value",
                code="INVALID_VALUE",
                message="Target/stop-loss value must be greater than zero"
            ))

def validate_time(time_str: str, path: str, errors: List[StrategyValidationError]) -> None:
    """Verifies that time string is in valid HH:MM format."""
    if not time_str or not time_str.strip():
        errors.append(StrategyValidationError(
            field=path,
            code="TIME_REQUIRED",
            message="Time is required"
        ))
        return
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        errors.append(StrategyValidationError(
            field=path,
            code="INVALID_TIME_FORMAT",
            message="Time must be in HH:mm format"
        ))

def validate_strategy_request(request: StrategyRequest) -> StrategyValidationResponse:
    """Validates structural constraints of a strategy request, matching original Java logic."""
    errors: List[StrategyValidationError] = []

    # 1. Basic Fields
    if not request.name or not request.name.strip():
        errors.append(StrategyValidationError(field="name", code="NAME_REQUIRED", message="Strategy name is required"))
    elif len(request.name) < 3 or len(request.name) > 255:
        errors.append(StrategyValidationError(field="name", code="INVALID_NAME_LENGTH", message="Name must be between 3 and 255 characters"))

    if not request.underlying or str(request.underlying).upper().strip() not in SUPPORTED_UNDERLYINGS:
        errors.append(StrategyValidationError(field="underlying", code="INVALID_UNDERLYING", message=f"Underlying must be one of: {', '.join(sorted(SUPPORTED_UNDERLYINGS))}"))

    if request.capital is None or request.capital <= Decimal("0.00"):
        errors.append(StrategyValidationError(field="capital", code="INVALID_CAPITAL", message="Capital must be greater than zero"))

    if not request.tradingType or request.tradingType.upper() not in SUPPORTED_TRADING_TYPES:
        errors.append(StrategyValidationError(field="tradingType", code="INVALID_TRADING_TYPE", message="Trading type must be INTRADAY or DELIVERY"))

    # 2. Positions / Legs Validation
    if not request.legs:
        errors.append(StrategyValidationError(field="positions", code="POSITIONS_REQUIRED", message="At least one position (leg) is required"))
    else:
        sequences: Set[int] = set()
        for idx, leg in enumerate(request.legs):
            prefix = f"positions[{idx}]."

            if leg.sequence is None:
                errors.append(StrategyValidationError(field=f"{prefix}sequence", code="SEQUENCE_REQUIRED", message="Sequence is required"))
            elif leg.sequence in sequences:
                errors.append(StrategyValidationError(field=f"{prefix}sequence", code="DUPLICATE_SEQUENCE", message="Leg sequence must be unique"))
            else:
                sequences.add(leg.sequence)

            if not leg.segment or leg.segment.upper() not in SUPPORTED_SEGMENTS:
                errors.append(StrategyValidationError(field=f"{prefix}segment", code="INVALID_SEGMENT", message="Segment must be OPT, EQ, or FUT"))

            if not leg.side or leg.side.upper() not in SUPPORTED_SIDES:
                errors.append(StrategyValidationError(field=f"{prefix}side", code="INVALID_SIDE", message="Side must be BUY or SELL"))

            if not leg.strikeSelection or leg.strikeSelection.upper() not in SUPPORTED_STRIKES:
                errors.append(StrategyValidationError(field=f"{prefix}strikeSelection", code="INVALID_STRIKE", message="Strike selection is invalid"))
            elif leg.strikeSelection.upper() == "CUSTOM" and leg.strikeValue is None:
                errors.append(StrategyValidationError(field=f"{prefix}value", code="CUSTOM_STRIKE_VALUE_REQUIRED", message="Value is required when strike is CUSTOM"))

            if not leg.expiry or leg.expiry.upper() not in SUPPORTED_EXPIRIES:
                errors.append(StrategyValidationError(field=f"{prefix}expiry", code="INVALID_EXPIRY", message="Expiry is invalid"))

            if leg.lots is None or leg.lots < 1:
                errors.append(StrategyValidationError(field=f"{prefix}lots", code="INVALID_LOTS", message="Lots must be at least 1"))

            validate_target_stop_loss(leg.targetValue, leg.targetType, f"{prefix}target", errors)
            validate_target_stop_loss(leg.stopLossValue, leg.stopLossType, f"{prefix}stopLoss", errors)

    # 3. Entry Settings
    if not request.entrySetting:
        errors.append(StrategyValidationError(field="entrySettings", code="ENTRY_SETTINGS_REQUIRED", message="Entry settings are required"))
    else:
        validate_time(request.entrySetting.entryTime, "entrySettings.entryTime", errors)

        if not request.entryDays:
            errors.append(StrategyValidationError(field="entrySettings.entryDays", code="ENTRY_DAYS_REQUIRED", message="At least one entry day is required"))
        else:
            for day in request.entryDays:
                if not day or day.upper() not in SUPPORTED_DAYS:
                    errors.append(StrategyValidationError(field="entrySettings.entryDays", code="INVALID_ENTRY_DAY", message="Entry day must be MONDAY, TUESDAY, WEDNESDAY, THURSDAY, or FRIDAY"))

    # 4. Exit Settings
    if not request.exitSetting:
        errors.append(StrategyValidationError(field="exitSettings", code="EXIT_SETTINGS_REQUIRED", message="Exit settings are required"))
    else:
        validate_time(request.exitSetting.exitTime, "exitSettings.exitTime", errors)
        validate_target_stop_loss(request.exitSetting.profitMtmValue, request.exitSetting.profitMtmType, "exitSettings.profitMtm", errors)
        validate_target_stop_loss(request.exitSetting.stopLossMtmValue, request.exitSetting.stopLossMtmType, "exitSettings.stopLossMtm", errors)

    return StrategyValidationResponse(
        valid=len(errors) == 0,
        errors=errors
    )
