"""
Calculation Engine — Technical Indicators
Pure pandas/numpy implementations of all supported indicators.
No external TA library dependency — fully self-contained.

Indicators:
  RSI, MACD, Stochastic, Supertrend, ADX (+DI/-DI),
  CCI, MFI, Bollinger Bands, VWAP, EMA (9/20/50/200),
  Volume analysis, Ichimoku Cloud
"""
from __future__ import annotations
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Candle helper — expects list of dicts with keys: open, high, low, close, volume
# ---------------------------------------------------------------------------

def _col(candles: List[Dict], key: str) -> List[float]:
    """Extract a column from candle list, returning floats."""
    return [float(c.get(key, 0) or 0) for c in candles]


def _ema_series(values: List[float], period: int) -> List[float]:
    """Compute EMA series for a list of floats."""
    if not values or period <= 0:
        return []
    result = [None] * len(values)
    k = 2.0 / (period + 1)
    # Seed with SMA for the first period
    start = period - 1
    if start >= len(values):
        return result
    sma = sum(values[:period]) / period
    result[start] = sma
    for i in range(start + 1, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def _sma(values: List[float], period: int) -> Optional[float]:
    """Simple moving average of last `period` values."""
    tail = [v for v in values[-period:] if v is not None]
    return sum(tail) / len(tail) if len(tail) == period else None


def _rma_series(values: List[float], period: int) -> List[float]:
    """Wilder's Smoothed Moving Average (RMA) — used in RSI, ATR, ADX."""
    result = [None] * len(values)
    if len(values) < period:
        return result
    # Seed
    result[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        result[i] = (result[i - 1] * (period - 1) + values[i]) / period
    return result


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def calc_rsi(candles: List[Dict], period: int = 14) -> Dict:
    closes = _col(candles, "close")
    if len(closes) < period + 1:
        return {"name": "RSI", "display_name": f"RSI ({period})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain_s = _rma_series(gains, period)
    avg_loss_s = _rma_series(losses, period)

    rsi_series = []
    for g, l in zip(avg_gain_s, avg_loss_s):
        if g is None or l is None:
            rsi_series.append(None)
        elif l == 0:
            rsi_series.append(100.0)
        else:
            rs = g / l
            rsi_series.append(round(100 - 100 / (1 + rs), 2))

    rsi_vals = [v for v in rsi_series if v is not None]
    if not rsi_vals:
        return {"name": "RSI", "display_name": f"RSI ({period})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    current = rsi_vals[-1]
    history = rsi_vals[-20:]

    if current <= 30:
        signal, color, desc = "BUY", "green", f"Oversold ({current:.1f}) — potential reversal up"
    elif current >= 70:
        signal, color, desc = "SELL", "red", f"Overbought ({current:.1f}) — potential reversal down"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Neutral zone ({current:.1f})"

    return {"name": "RSI", "display_name": f"RSI ({period})", "value": current, "signal": signal, "signal_color": color, "description": desc, "history": history}


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def calc_macd(candles: List[Dict], fast: int = 12, slow: int = 26, signal_period: int = 9) -> Dict:
    closes = _col(candles, "close")
    if len(closes) < slow + signal_period:
        return {"name": "MACD", "display_name": f"MACD ({fast},{slow},{signal_period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)

    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)

    valid_macd = [v for v in macd_line if v is not None]
    if not valid_macd:
        return {"name": "MACD", "display_name": f"MACD ({fast},{slow},{signal_period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    signal_series = _ema_series(valid_macd, signal_period)
    sig_vals = [v for v in signal_series if v is not None]
    if not sig_vals:
        return {"name": "MACD", "display_name": f"MACD ({fast},{slow},{signal_period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    macd_val = round(valid_macd[-1], 4)
    sig_val = round(sig_vals[-1], 4)
    hist = round(macd_val - sig_val, 4)

    history = [round(v, 4) for v in valid_macd[-20:]]

    if macd_val > sig_val and hist > 0:
        signal, color, desc = "BUY", "green", f"MACD above signal — bullish momentum (hist: {hist:+.3f})"
    elif macd_val < sig_val and hist < 0:
        signal, color, desc = "SELL", "red", f"MACD below signal — bearish momentum (hist: {hist:+.3f})"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"MACD crossover zone (hist: {hist:+.3f})"

    return {
        "name": "MACD", "display_name": f"MACD ({fast},{slow},{signal_period})",
        "value": macd_val,
        "secondary": {"signal_line": sig_val, "histogram": hist},
        "signal": signal, "signal_color": color, "description": desc,
        "history": history
    }


# ---------------------------------------------------------------------------
# Stochastic Oscillator (%K, %D)
# ---------------------------------------------------------------------------

def calc_stochastic(candles: List[Dict], k_period: int = 14, d_period: int = 3) -> Dict:
    highs = _col(candles, "high")
    lows = _col(candles, "low")
    closes = _col(candles, "close")
    if len(closes) < k_period + d_period:
        return {"name": "STOCH", "display_name": f"Stochastic ({k_period},{d_period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    k_series = []
    for i in range(k_period - 1, len(closes)):
        window_high = max(highs[i - k_period + 1: i + 1])
        window_low = min(lows[i - k_period + 1: i + 1])
        rng = window_high - window_low
        k = ((closes[i] - window_low) / rng * 100) if rng != 0 else 50.0
        k_series.append(round(k, 2))

    if len(k_series) < d_period:
        return {"name": "STOCH", "display_name": f"Stochastic ({k_period},{d_period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    d_series = _ema_series(k_series, d_period)
    d_vals = [v for v in d_series if v is not None]

    k_val = k_series[-1]
    d_val = round(d_vals[-1], 2) if d_vals else None
    history = k_series[-20:]

    if k_val < 20:
        signal, color, desc = "BUY", "green", f"Oversold — %K={k_val:.1f}, %D={d_val:.1f}"
    elif k_val > 80:
        signal, color, desc = "SELL", "red", f"Overbought — %K={k_val:.1f}, %D={d_val:.1f}"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Neutral — %K={k_val:.1f}, %D={d_val:.1f}"

    return {
        "name": "STOCH", "display_name": f"Stochastic ({k_period},{d_period})",
        "value": k_val,
        "secondary": {"k": k_val, "d": d_val},
        "signal": signal, "signal_color": color, "description": desc,
        "history": history
    }


# ---------------------------------------------------------------------------
# Supertrend
# ---------------------------------------------------------------------------

def calc_supertrend(candles: List[Dict], period: int = 10, multiplier: float = 3.0) -> Dict:
    highs = _col(candles, "high")
    lows = _col(candles, "low")
    closes = _col(candles, "close")
    if len(closes) < period + 1:
        return {"name": "SUPERTREND", "display_name": f"Supertrend ({period},{multiplier})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    # True Range
    tr = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, len(closes))]
    tr.insert(0, highs[0] - lows[0])

    atr_series = _rma_series(tr, period)

    upper_band = [None] * len(closes)
    lower_band = [None] * len(closes)
    supertrend = [None] * len(closes)
    direction = [1] * len(closes)  # 1=bullish, -1=bearish

    for i in range(period - 1, len(closes)):
        hl2 = (highs[i] + lows[i]) / 2
        atr = atr_series[i]
        if atr is None:
            continue
        ub = hl2 + multiplier * atr
        lb = hl2 - multiplier * atr

        upper_band[i] = ub
        lower_band[i] = lb

        if i == period - 1:
            supertrend[i] = ub
            direction[i] = -1
        else:
            prev_st = supertrend[i - 1]
            prev_dir = direction[i - 1]
            if prev_st is None:
                supertrend[i] = ub
                direction[i] = -1
                continue

            if prev_dir == -1:
                lb = max(lb, lower_band[i - 1] or lb)
            if prev_dir == 1:
                ub = min(ub, upper_band[i - 1] or ub)

            if closes[i] > prev_st:
                direction[i] = 1
                supertrend[i] = lb
            elif closes[i] < prev_st:
                direction[i] = -1
                supertrend[i] = ub
            else:
                direction[i] = prev_dir
                supertrend[i] = prev_st

    st_vals = [v for v in supertrend if v is not None]

    if not st_vals:
        return {"name": "SUPERTREND", "display_name": f"Supertrend ({period},{multiplier})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    current_st = round(st_vals[-1], 2)
    current_dir = direction[-1]

    if current_dir == 1:
        signal, color, desc = "BUY", "green", f"Uptrend — price above Supertrend ({current_st:.2f})"
    else:
        signal, color, desc = "SELL", "red", f"Downtrend — price below Supertrend ({current_st:.2f})"

    return {
        "name": "SUPERTREND", "display_name": f"Supertrend ({period},{multiplier})",
        "value": current_st,
        "secondary": {"direction": current_dir},
        "signal": signal, "signal_color": color, "description": desc,
        "history": [round(v, 2) for v in st_vals[-20:]]
    }


# ---------------------------------------------------------------------------
# ADX (Average Directional Index)
# ---------------------------------------------------------------------------

def calc_adx(candles: List[Dict], period: int = 14) -> Dict:
    highs = _col(candles, "high")
    lows = _col(candles, "low")
    closes = _col(candles, "close")
    if len(closes) < period * 2:
        return {"name": "ADX", "display_name": f"ADX ({period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    tr, plus_dm, minus_dm = [], [], []
    for i in range(1, len(closes)):
        h_diff = highs[i] - highs[i - 1]
        l_diff = lows[i - 1] - lows[i]
        tr_val = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr.append(tr_val)
        plus_dm.append(max(h_diff, 0) if h_diff > l_diff else 0)
        minus_dm.append(max(l_diff, 0) if l_diff > h_diff else 0)

    atr_s = _rma_series(tr, period)
    pdi_s = _rma_series(plus_dm, period)
    mdi_s = _rma_series(minus_dm, period)

    dx_series = []
    for atr, pdi, mdi in zip(atr_s, pdi_s, mdi_s):
        if atr and atr != 0 and pdi is not None and mdi is not None:
            plus_di = (pdi / atr) * 100
            minus_di = (mdi / atr) * 100
            denom = plus_di + minus_di
            dx = (abs(plus_di - minus_di) / denom * 100) if denom != 0 else 0
            dx_series.append(dx)
        else:
            dx_series.append(None)

    dx_valid = [v for v in dx_series if v is not None]
    if not dx_valid:
        return {"name": "ADX", "display_name": f"ADX ({period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    adx_series = _rma_series(dx_valid, period)
    adx_valid = [v for v in adx_series if v is not None]
    if not adx_valid:
        return {"name": "ADX", "display_name": f"ADX ({period})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    current_adx = round(adx_valid[-1], 2)
    last_atr = atr_s[-1] or 1
    plus_di_cur = round((pdi_s[-1] / last_atr) * 100, 2) if pdi_s[-1] else 0
    minus_di_cur = round((mdi_s[-1] / last_atr) * 100, 2) if mdi_s[-1] else 0

    if current_adx >= 25 and plus_di_cur > minus_di_cur:
        signal, color, desc = "BUY", "green", f"Strong uptrend — ADX={current_adx:.1f}, +DI>{minus_di_cur:.1f}"
    elif current_adx >= 25 and minus_di_cur > plus_di_cur:
        signal, color, desc = "SELL", "red", f"Strong downtrend — ADX={current_adx:.1f}, -DI>{plus_di_cur:.1f}"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Weak/no trend — ADX={current_adx:.1f}"

    return {
        "name": "ADX", "display_name": f"ADX ({period})",
        "value": current_adx,
        "secondary": {"plus_di": plus_di_cur, "minus_di": minus_di_cur},
        "signal": signal, "signal_color": color, "description": desc,
        "history": [round(v, 2) for v in adx_valid[-20:]]
    }


# ---------------------------------------------------------------------------
# CCI (Commodity Channel Index)
# ---------------------------------------------------------------------------

def calc_cci(candles: List[Dict], period: int = 20) -> Dict:
    highs = _col(candles, "high")
    lows = _col(candles, "low")
    closes = _col(candles, "close")
    if len(closes) < period:
        return {"name": "CCI", "display_name": f"CCI ({period})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    typical = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    cci_series = []
    for i in range(period - 1, len(typical)):
        tp_window = typical[i - period + 1: i + 1]
        ma = sum(tp_window) / period
        mean_dev = sum(abs(t - ma) for t in tp_window) / period
        cci = ((typical[i] - ma) / (0.015 * mean_dev)) if mean_dev != 0 else 0
        cci_series.append(round(cci, 2))

    if not cci_series:
        return {"name": "CCI", "display_name": f"CCI ({period})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    current = cci_series[-1]
    if current >= 100:
        signal, color, desc = "BUY", "green", f"Overbought zone ({current:.0f}) — strong bullish momentum"
    elif current <= -100:
        signal, color, desc = "SELL", "red", f"Oversold zone ({current:.0f}) — strong bearish momentum"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Neutral ({current:.0f})"

    return {"name": "CCI", "display_name": f"CCI ({period})", "value": current, "signal": signal, "signal_color": color, "description": desc, "history": cci_series[-20:]}


# ---------------------------------------------------------------------------
# MFI (Money Flow Index)
# ---------------------------------------------------------------------------

def calc_mfi(candles: List[Dict], period: int = 14) -> Dict:
    highs = _col(candles, "high")
    lows = _col(candles, "low")
    closes = _col(candles, "close")
    volumes = _col(candles, "volume")
    if len(closes) < period + 1:
        return {"name": "MFI", "display_name": f"MFI ({period})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    typical = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    raw_mf = [t * v for t, v in zip(typical, volumes)]

    mfi_series = []
    for i in range(period, len(typical)):
        pos_mf = sum(raw_mf[j] for j in range(i - period, i) if typical[j] >= typical[j - 1])
        neg_mf = sum(raw_mf[j] for j in range(i - period, i) if typical[j] < typical[j - 1])
        mfr = pos_mf / neg_mf if neg_mf != 0 else 100
        mfi = 100 - (100 / (1 + mfr))
        mfi_series.append(round(mfi, 2))

    if not mfi_series:
        return {"name": "MFI", "display_name": f"MFI ({period})", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    current = mfi_series[-1]
    if current <= 20:
        signal, color, desc = "BUY", "green", f"Oversold with volume ({current:.1f}) — buying pressure"
    elif current >= 80:
        signal, color, desc = "SELL", "red", f"Overbought with volume ({current:.1f}) — selling pressure"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Neutral ({current:.1f})"

    return {"name": "MFI", "display_name": f"MFI ({period})", "value": current, "signal": signal, "signal_color": color, "description": desc, "history": mfi_series[-20:]}


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def calc_bollinger_bands(candles: List[Dict], period: int = 20, std_dev: float = 2.0) -> Dict:
    closes = _col(candles, "close")
    if len(closes) < period:
        return {"name": "BB", "display_name": f"Bollinger Bands ({period},{std_dev})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data", "history": []}

    bb_series = []
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        ma = sum(window) / period
        std = math.sqrt(sum((v - ma) ** 2 for v in window) / period)
        upper = round(ma + std_dev * std, 2)
        lower = round(ma - std_dev * std, 2)
        ma = round(ma, 2)
        width = round(upper - lower, 2)
        pct_b = round((closes[i] - lower) / width, 4) if width != 0 else 0.5
        bb_series.append({"upper": upper, "middle": ma, "lower": lower, "width": width, "pct_b": pct_b, "close": closes[i]})

    if not bb_series:
        return {"name": "BB", "display_name": f"Bollinger Bands ({period},{std_dev})", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Calculating...", "history": []}

    last = bb_series[-1]
    current_close = last["close"]
    pct_b = last["pct_b"]

    if current_close <= last["lower"]:
        signal, color, desc = "BUY", "green", f"Price at lower band — potential bounce (lower: {last['lower']:.2f})"
    elif current_close >= last["upper"]:
        signal, color, desc = "SELL", "red", f"Price at upper band — potential reversal (upper: {last['upper']:.2f})"
    elif pct_b < 0.2:
        signal, color, desc = "BUY", "green", f"Near lower band %B={pct_b:.2f} — bullish zone"
    elif pct_b > 0.8:
        signal, color, desc = "SELL", "red", f"Near upper band %B={pct_b:.2f} — bearish zone"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Mid-band zone %B={pct_b:.2f}"

    return {
        "name": "BB", "display_name": f"Bollinger Bands ({period},{std_dev})",
        "value": last["middle"],
        "secondary": {"upper": last["upper"], "lower": last["lower"], "width": last["width"], "pct_b": pct_b},
        "signal": signal, "signal_color": color, "description": desc,
        "history": [b["middle"] for b in bb_series[-20:]]
    }


# ---------------------------------------------------------------------------
# VWAP (Volume Weighted Average Price) — Session-based
# ---------------------------------------------------------------------------

def calc_vwap(candles: List[Dict]) -> Dict:
    """Session VWAP — calculates over all candles provided (assumed to be same day)."""
    highs = _col(candles, "high")
    lows = _col(candles, "low")
    closes = _col(candles, "close")
    volumes = _col(candles, "volume")
    if not candles:
        return {"name": "VWAP", "display_name": "VWAP (Session)", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "No data", "history": []}

    typical = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    cumulative_tpv = 0.0
    cumulative_vol = 0.0
    vwap_series = []
    for tp, vol in zip(typical, volumes):
        cumulative_tpv += tp * vol
        cumulative_vol += vol
        vwap = cumulative_tpv / cumulative_vol if cumulative_vol != 0 else tp
        vwap_series.append(round(vwap, 2))

    current_vwap = vwap_series[-1]
    current_close = closes[-1]

    if current_close > current_vwap:
        signal, color, desc = "BUY", "green", f"Price above VWAP ({current_vwap:.2f}) — bullish bias"
    elif current_close < current_vwap:
        signal, color, desc = "SELL", "red", f"Price below VWAP ({current_vwap:.2f}) — bearish bias"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Price at VWAP ({current_vwap:.2f})"

    return {
        "name": "VWAP", "display_name": "VWAP (Session)",
        "value": current_vwap, "signal": signal, "signal_color": color,
        "description": desc, "history": vwap_series[-20:]
    }


# ---------------------------------------------------------------------------
# EMA (Multiple periods)
# ---------------------------------------------------------------------------

def calc_ema(candles: List[Dict], periods: Optional[List[int]] = None) -> Dict:
    closes = _col(candles, "close")
    if periods is None:
        periods = [8, 9, 20, 33, 50, 200]

    results = {}
    for period in periods:
        series = _ema_series(closes, period)
        vals = [v for v in series if v is not None]
        results[f"ema{period}"] = round(vals[-1], 2) if vals else None

    # Signals: Check 8 vs 33 and 9 vs 20 EMA
    e8 = results.get("ema8")
    e33 = results.get("ema33")
    e9 = results.get("ema9")
    e20 = results.get("ema20")
    e50 = results.get("ema50")

    if e8 is not None and e33 is not None and e8 > e33:
        signal, color, desc = "BUY", "green", f"EMA8 ({e8:.2f}) > EMA33 ({e33:.2f}) — bullish alignment"
    elif e8 is not None and e33 is not None and e8 < e33:
        signal, color, desc = "SELL", "red", f"EMA8 ({e8:.2f}) < EMA33 ({e33:.2f}) — bearish alignment"
    elif e9 is not None and e20 is not None and e9 > e20:
        signal, color, desc = "BUY", "green", f"EMA9 ({e9:.2f}) > EMA20 ({e20:.2f}) — bullish crossover"
    elif e9 is not None and e20 is not None and e9 < e20:
        signal, color, desc = "SELL", "red", f"EMA9 ({e9:.2f}) < EMA20 ({e20:.2f}) — bearish crossover"
    else:
        signal, color, desc = "NEUTRAL", "amber", "EMA alignment neutral"

    return {
        "name": "EMA",
        "display_name": "EMA (8/9/20/33/50/200)",
        "value": e8 or e20,
        "secondary": results,
        "signal": signal,
        "signal_color": color,
        "description": desc,
        "history": []
    }


# ---------------------------------------------------------------------------
# Volume Analysis
# ---------------------------------------------------------------------------

def calc_volume(candles: List[Dict], avg_period: int = 20) -> Dict:
    volumes = _col(candles, "volume")
    if not volumes:
        return {"name": "VOLUME", "display_name": "Volume Analysis", "value": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "No data", "history": []}

    current_vol = volumes[-1]
    avg_vol = sum(volumes[-avg_period:]) / min(len(volumes), avg_period)
    ratio = round(current_vol / avg_vol, 2) if avg_vol != 0 else 1.0

    if ratio >= 2.0:
        signal, color, desc = "BUY", "green", f"Volume spike {ratio:.1f}x avg — high conviction move"
    elif ratio >= 1.5:
        signal, color, desc = "BUY", "green", f"Above avg volume {ratio:.1f}x — confirmed momentum"
    elif ratio < 0.5:
        signal, color, desc = "NEUTRAL", "amber", f"Low volume {ratio:.1f}x avg — weak move"
    else:
        signal, color, desc = "NEUTRAL", "amber", f"Normal volume {ratio:.1f}x avg"

    return {
        "name": "VOLUME", "display_name": f"Volume (vs {avg_period}-bar avg)",
        "value": round(current_vol, 0),
        "secondary": {"avg_volume": round(avg_vol, 0), "ratio": ratio},
        "signal": signal, "signal_color": color, "description": desc,
        "history": [round(v, 0) for v in volumes[-20:]]
    }


# ---------------------------------------------------------------------------
# Ichimoku Cloud
# ---------------------------------------------------------------------------

def calc_ichimoku(candles: List[Dict], tenkan_period: int = 9, kijun_period: int = 26, senkou_b_period: int = 52) -> Dict:
    highs = _col(candles, "high")
    lows = _col(candles, "low")
    closes = _col(candles, "close")
    if len(closes) < senkou_b_period:
        return {"name": "ICHIMOKU", "display_name": "Ichimoku Cloud", "value": None, "secondary": None, "signal": "NEUTRAL", "signal_color": "amber", "description": "Insufficient data (need 52+ candles)", "history": []}

    def midpoint(h_list, l_list, period, idx):
        if idx < period - 1:
            return None
        h_max = max(h_list[idx - period + 1: idx + 1])
        l_min = min(l_list[idx - period + 1: idx + 1])
        return (h_max + l_min) / 2

    i = len(closes) - 1
    tenkan = midpoint(highs, lows, tenkan_period, i)
    kijun = midpoint(highs, lows, kijun_period, i)
    senkou_a = ((tenkan + kijun) / 2) if tenkan and kijun else None
    senkou_b = midpoint(highs, lows, senkou_b_period, i)
    chikou = closes[-1]

    current_price = closes[-1]
    cloud_top = max(senkou_a or 0, senkou_b or 0)
    cloud_bottom = min(senkou_a or 0, senkou_b or 0)

    if current_price > cloud_top:
        signal, color, desc = "BUY", "green", f"Price above cloud — strong bullish"
    elif current_price < cloud_bottom:
        signal, color, desc = "SELL", "red", f"Price below cloud — strong bearish"
    else:
        signal, color, desc = "NEUTRAL", "amber", "Price inside cloud — uncertain"

    secondary = {
        "tenkan": round(tenkan, 2) if tenkan else None,
        "kijun": round(kijun, 2) if kijun else None,
        "senkou_a": round(senkou_a, 2) if senkou_a else None,
        "senkou_b": round(senkou_b, 2) if senkou_b else None,
        "chikou": round(chikou, 2),
        "cloud_top": round(cloud_top, 2),
        "cloud_bottom": round(cloud_bottom, 2)
    }

    return {
        "name": "ICHIMOKU", "display_name": "Ichimoku Cloud",
        "value": round(kijun, 2) if kijun else None,
        "secondary": secondary,
        "signal": signal, "signal_color": color, "description": desc,
        "history": []
    }


# ---------------------------------------------------------------------------
# Master: compute ALL indicators from a candle list
# ---------------------------------------------------------------------------

def compute_all_indicators(
    candles: List[Dict],
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    ltp: Optional[float] = None,
    vwap: Optional[float] = None,
    data_source: Optional[str] = None,
) -> Any:
    """
    Runs all indicator calculations on the given candle window.
    If symbol is provided, returns a full snapshot dict.
    Otherwise returns list of indicator dicts.
    """
    if len(candles) < 5:
        return {"symbol": symbol, "indicators": []} if symbol else []

    results = []
    calculators = [
        calc_rsi,
        calc_macd,
        calc_stochastic,
        calc_supertrend,
        calc_adx,
        calc_cci,
        calc_mfi,
        calc_bollinger_bands,
        calc_vwap,
        calc_ema,
        calc_volume,
        calc_ichimoku,
    ]

    for fn in calculators:
        try:
            result = fn(candles)
            results.append(result)
            if result.get("name") == "EMA" and isinstance(result.get("secondary"), dict):
                for p_key, p_val in result["secondary"].items():
                    period_num = p_key.replace("ema", "")
                    results.append({
                        "name": f"EMA_{period_num}",
                        "display_name": f"EMA ({period_num})",
                        "value": p_val,
                        "signal": result.get("signal", "NEUTRAL"),
                        "signal_color": result.get("signal_color", "amber"),
                        "description": f"EMA {period_num} period value: {p_val}",
                        "history": []
                    })
        except Exception as e:
            logger.warning("Indicator %s failed: %s", fn.__name__, str(e))

    if symbol is not None:
        last_close = candles[-1]["close"] if candles else None
        calc_v = vwap
        if calc_v is None:
            for r in results:
                if r.get("name") == "VWAP":
                    calc_v = r.get("value")
                    break

        return {
            "symbol": symbol,
            "timeframe": timeframe or "5m",
            "ltp": ltp or last_close,
            "vwap": calc_v,
            "indicators": results,
            "candle_count": len(candles),
            "is_market_hours": True,
            "data_source": data_source or "DHAN",
        }

    return results
