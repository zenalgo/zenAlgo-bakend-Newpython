"""
Single source of truth for strategy Target Profit & Stop Loss exit calculations.
Supports percentage-of-entry-price, fixed points, BUY and SELL directions,
tick size normalization, market data freshness validation, IST EOD cutoff,
and provides consistent target price, stop loss price, target profit (₹),
max risk (₹), live PnL, target progress %, and trigger state evaluation.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple, Any, Dict, Union
from datetime import datetime, timezone
from decimal import Decimal
import re
import math
import logging
import pytz

logger = logging.getLogger(__name__)

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")

@dataclass
class ExitLevels:
    target_price: float
    target_profit: float
    stop_loss_price: float
    max_risk: float
    target_val: float
    target_type: str
    sl_val: float
    sl_type: str
    current_pnl: float
    is_target_met: bool
    is_sl_met: bool
    progress_pct: float
    direction: str
    actual_fill_price: float
    quantity: int
    current_ltp: float
    tick_size: float = 0.01
    exit_reason: Optional[str] = None


def round_to_tick(price: float, tick_size: float = 0.01) -> float:
    """Rounds price to nearest valid precision or tick size (default 2 decimal places)."""
    if tick_size <= 0:
        return round(price, 2)
    if tick_size == 0.01:
        return round(price, 2)
    num_ticks = round(price / tick_size)
    return round(num_ticks * tick_size, 2)


def validate_market_quote_freshness(
    quote: Dict[str, Any],
    expected_symbol: Optional[str] = None,
    max_age_seconds: float = 60.0
) -> Tuple[bool, str]:
    """
    Validates market quote for:
    1. Presence and non-null quote dictionary.
    2. Valid positive LTP (not null, <= 0, NaN, or Inf).
    3. Instrument symbol match if expected_symbol provided.
    4. Data freshness timestamp within max_age_seconds.
    """
    if not quote or not isinstance(quote, dict):
        return False, "REJECTED: Empty or invalid market quote object."

    ltp = None
    for k in ("currentLtp", "ltp", "price", "last_price"):
        if k in quote and quote[k] is not None:
            ltp = quote[k]
            break

    if ltp is None:
        return False, "REJECTED: Quote contains no LTP / price field."

    try:
        ltp_val = float(ltp)
        if ltp_val <= 0 or math.isnan(ltp_val) or math.isinf(ltp_val):
            return False, f"REJECTED: Non-positive or invalid LTP value: {ltp_val}"
    except (ValueError, TypeError):
        return False, f"REJECTED: Unparseable LTP value: {ltp}"

    # Symbol / Contract matching
    if expected_symbol:
        actual_symbol = str(quote.get("symbol") or quote.get("tradingsymbol") or "").upper().replace(" ", "")
        norm_expected = str(expected_symbol).upper().replace(" ", "")
        if actual_symbol and norm_expected and actual_symbol != norm_expected:
            return False, f"REJECTED: Instrument mismatch. Expected '{norm_expected}' but got quote for '{actual_symbol}'."

    # Timestamp freshness
    quote_ts = quote.get("timestamp") or quote.get("quote_timestamp")
    if quote_ts:
        now_utc = datetime.now(timezone.utc)
        if isinstance(quote_ts, (int, float)):
            age_sec = now_utc.timestamp() - quote_ts
        elif isinstance(quote_ts, datetime):
            if quote_ts.tzinfo is None:
                quote_ts = quote_ts.replace(tzinfo=timezone.utc)
            age_sec = (now_utc - quote_ts).total_seconds()
        else:
            age_sec = 0.0

        if age_sec > max_age_seconds:
            return False, f"REJECTED: Stale market data tick (Age: {age_sec:.1f}s > threshold {max_age_seconds}s)."

    return True, "VALID"


def extract_target_and_sl_config(builder: dict, version: Optional[Any] = None) -> Tuple[float, str, float, str]:
    """
    Extracts configured target value/type and stop loss value/type from builder params
    or version relational fields. Default is target = 2.0 (PERCENTAGE) and sl = 1.0 (PERCENTAGE).
    """
    # 1. Target config extraction
    target_val = 2.0
    target_type = "PERCENTAGE"
    
    t_cfg = builder.get("target") if isinstance(builder, dict) else None
    if t_cfg:
        if hasattr(t_cfg, "value") and t_cfg.value is not None:
            try:
                target_val = float(t_cfg.value)
            except (ValueError, TypeError):
                target_val = 2.0
            target_type = str(getattr(t_cfg, "type", "PERCENTAGE") or "PERCENTAGE").upper().strip()
        elif isinstance(t_cfg, dict):
            raw_v = t_cfg.get("value")
            if raw_v is not None:
                try:
                    target_val = float(raw_v)
                except (ValueError, TypeError):
                    target_val = 2.0
            raw_t = t_cfg.get("type", "PERCENTAGE")
            target_type = str(raw_t or "PERCENTAGE").upper().strip()
        elif isinstance(t_cfg, (int, float)):
            target_val = float(t_cfg)
            target_type = "PERCENTAGE"
        elif isinstance(t_cfg, str):
            match = re.search(r"(\d+(\.\d+)?)", t_cfg)
            if match:
                target_val = float(match.group(1))
            target_type = "PERCENTAGE" if "%" in t_cfg else "POINTS"
    elif version and hasattr(version, "exit_setting") and version.exit_setting and version.exit_setting.profit_mtm_value is not None:
        target_val = float(version.exit_setting.profit_mtm_value)
        target_type = str(version.exit_setting.profit_mtm_type or "PERCENTAGE").upper().strip()

    # 2. Risk / Stop Loss config extraction
    sl_val = 1.0
    sl_type = "PERCENTAGE"

    r_cfg = builder.get("riskManagement") if isinstance(builder, dict) else None
    if r_cfg:
        if hasattr(r_cfg, "stopLoss") and r_cfg.stopLoss:
            sl_item = r_cfg.stopLoss
            if isinstance(sl_item, dict):
                raw_v = sl_item.get("value")
                if raw_v is not None:
                    try:
                        sl_val = float(raw_v)
                    except (ValueError, TypeError):
                        sl_val = 1.0
                sl_type = str(sl_item.get("type", "PERCENTAGE") or "PERCENTAGE").upper().strip()
            elif isinstance(sl_item, str):
                match = re.search(r"(\d+(\.\d+)?)", sl_item)
                if match:
                    sl_val = float(match.group(1))
                sl_type = "PERCENTAGE" if "%" in sl_item else "POINTS"
            elif hasattr(sl_item, "value"):
                sl_val = float(sl_item.value)
                sl_type = str(getattr(sl_item, "type", "PERCENTAGE") or "PERCENTAGE").upper().strip()
        if hasattr(r_cfg, "stopLossValue") and r_cfg.stopLossValue is not None:
            try:
                sl_val = float(r_cfg.stopLossValue)
            except (ValueError, TypeError):
                pass
            if hasattr(r_cfg, "stopLossType") and r_cfg.stopLossType:
                sl_type = str(r_cfg.stopLossType).upper().strip()
        elif isinstance(r_cfg, dict):
            if r_cfg.get("stopLossValue") is not None:
                try:
                    sl_val = float(r_cfg["stopLossValue"])
                except (ValueError, TypeError):
                    pass
            if r_cfg.get("stopLossType"):
                sl_type = str(r_cfg["stopLossType"]).upper().strip()
            elif r_cfg.get("value") is not None:
                try:
                    sl_val = float(r_cfg["value"])
                except (ValueError, TypeError):
                    pass
    elif version and hasattr(version, "exit_setting") and version.exit_setting and version.exit_setting.stop_loss_mtm_value is not None:
        sl_val = float(version.exit_setting.stop_loss_mtm_value)
        sl_type = str(version.exit_setting.stop_loss_mtm_type or "PERCENTAGE").upper().strip()

    return target_val, target_type, sl_val, sl_type


def calculate_exit_levels(
    entry_price: float,
    quantity: int,
    current_ltp: float,
    target_val: float = 2.0,
    target_type: str = "PERCENTAGE",
    sl_val: float = 1.0,
    sl_type: str = "PERCENTAGE",
    direction: str = "BUY",
    tick_size: float = 0.01
) -> ExitLevels:
    """
    Calculates target price, stop loss price, target profit (₹), max risk (₹),
    live PnL, progress %, and trigger states strictly using percentage of entry/fill price (or points).
    """
    entry_price = float(entry_price)
    quantity = int(quantity)
    current_ltp = float(current_ltp)
    direction = direction.upper().strip() if direction else "BUY"
    target_type = target_type.upper().strip() if target_type else "PERCENTAGE"
    sl_type = sl_type.upper().strip() if sl_type else "PERCENTAGE"

    if direction in ("BUY", "LONG"):
        # Target calculation (for Long: profit when price rises)
        if target_type == "PERCENTAGE":
            raw_target_price = entry_price * (1.0 + (target_val / 100.0))
            target_price = round_to_tick(raw_target_price, tick_size)
            target_profit = round((target_price - entry_price) * quantity, 2)
        else: # POINTS
            target_price = round_to_tick(entry_price + target_val, tick_size)
            target_profit = round(target_val * quantity, 2)

        # Stop loss calculation (for Long: loss when price drops)
        if sl_type == "PERCENTAGE":
            raw_sl_price = entry_price * (1.0 - (sl_val / 100.0))
            stop_loss_price = round_to_tick(raw_sl_price, tick_size)
            max_risk = round((stop_loss_price - entry_price) * quantity, 2)
        else: # POINTS
            stop_loss_price = round_to_tick(entry_price - sl_val, tick_size)
            max_risk = round(-1.0 * sl_val * quantity, 2)

        current_pnl = round((current_ltp - entry_price) * quantity, 2)
        is_target_met = (current_ltp >= target_price) or (current_pnl >= target_profit and target_profit > 0)
        is_sl_met = (current_ltp <= stop_loss_price) or (current_pnl <= max_risk and max_risk < 0)

    else: # SELL / SHORT
        # Target calculation (for Short: profit when price falls)
        if target_type == "PERCENTAGE":
            raw_target_price = entry_price * (1.0 - (target_val / 100.0))
            target_price = round_to_tick(raw_target_price, tick_size)
            target_profit = round((entry_price - target_price) * quantity, 2)
        else: # POINTS
            target_price = round_to_tick(entry_price - target_val, tick_size)
            target_profit = round(target_val * quantity, 2)

        # Stop loss calculation (for Short: loss when price rises)
        if sl_type == "PERCENTAGE":
            raw_sl_price = entry_price * (1.0 + (sl_val / 100.0))
            stop_loss_price = round_to_tick(raw_sl_price, tick_size)
            max_risk = round((entry_price - stop_loss_price) * quantity, 2)
        else: # POINTS
            stop_loss_price = round_to_tick(entry_price + sl_val, tick_size)
            max_risk = round(-1.0 * sl_val * quantity, 2)

        current_pnl = round((entry_price - current_ltp) * quantity, 2)
        is_target_met = (current_ltp <= target_price) or (current_pnl >= target_profit and target_profit > 0)
        is_sl_met = (current_ltp >= stop_loss_price) or (current_pnl <= max_risk and max_risk < 0)

    # Calculate Target Progress %
    if is_target_met or (target_profit > 0 and current_pnl >= target_profit):
        progress_pct = 100.0
    elif target_profit > 0 and current_pnl > 0:
        progress_pct = round((current_pnl / target_profit) * 100.0, 1)
    else:
        progress_pct = 0.0

    exit_reason = None
    if is_target_met:
        exit_reason = f"🎯 TARGET PROFIT HIT: +₹{current_pnl:.2f} (LTP ₹{current_ltp:.2f} >= Target ₹{target_price:.2f})"
    elif is_sl_met:
        exit_reason = f"🛑 STOP LOSS HIT: ₹{current_pnl:.2f} (LTP ₹{current_ltp:.2f} <= SL ₹{stop_loss_price:.2f})"

    return ExitLevels(
        target_price=target_price,
        target_profit=target_profit,
        stop_loss_price=stop_loss_price,
        max_risk=max_risk,
        target_val=target_val,
        target_type=target_type,
        sl_val=sl_val,
        sl_type=sl_type,
        current_pnl=current_pnl,
        is_target_met=is_target_met,
        is_sl_met=is_sl_met,
        progress_pct=progress_pct,
        direction=direction,
        actual_fill_price=entry_price,
        quantity=quantity,
        current_ltp=current_ltp,
        tick_size=tick_size,
        exit_reason=exit_reason
    )


def is_eod_cutoff_reached(cutoff_time_str: str = "15:15") -> bool:
    """Evaluates whether current time in Asia/Kolkata (IST) has reached or passed EOD cutoff."""
    now_ist = datetime.now(KOLKATA_TZ)
    try:
        parts = cutoff_time_str.split(":")
        c_hour = int(parts[0])
        c_min = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        c_hour, c_min = 15, 15

    # During normal intraday trading hours (09:15 to 15:30)
    if now_ist.hour > c_hour or (now_ist.hour == c_hour and now_ist.minute >= c_min):
        return True
    return False
