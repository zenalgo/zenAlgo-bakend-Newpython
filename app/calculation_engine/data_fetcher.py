"""
Calculation Engine — Historical & Live Candle Data Fetcher
Dual-source data ingestion:
  1. Dhan REST API (/v2/charts/intraday or /v2/charts/historical) — Primary
  2. yfinance — Automatic fallback if Dhan is unavailable, credentials missing, or off-hours
"""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, Any, List, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Underlying ticker mapping for Yahoo Finance
YAHOO_TICKER_MAP: Dict[str, str] = {
    "NIFTY": "^NSEI",
    "NIFTY 50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "NIFTY BANK": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
    "SENSEX": "^BSESN",
    "BANKEX": "^BSEBANK",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "ITC": "ITC.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "LT": "LT.NS",
    "AXISBANK": "AXISBANK.NS",
}

# Dhan timeframe mapping
DHAN_INTERVAL_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "25m": "25",
    "60m": "60",
    "1h": "60",
    "1d": "D",
}

# Yahoo timeframe mapping
YF_INTERVAL_MAP = {
    "1m": ("1m", "5d"),
    "5m": ("5m", "5d"),
    "15m": ("15m", "1mo"),
    "25m": ("15m", "1mo"),
    "60m": ("60m", "1mo"),
    "1h": ("60m", "1mo"),
    "1d": ("1d", "1y"),
}


def get_yahoo_ticker(symbol: str) -> str:
    """Resolve standard trading symbol to Yahoo Finance ticker."""
    clean = symbol.strip().upper()
    if clean in YAHOO_TICKER_MAP:
        return YAHOO_TICKER_MAP[clean]
    if clean.endswith(".NS") or clean.endswith(".BO") or clean.startswith("^"):
        return clean
    return f"{clean}.NS"


async def fetch_candles_dhan(
    security_id: str,
    exchange_segment: str = "NSE_EQ",
    instrument: str = "EQUITY",
    timeframe: str = "5m",
    credentials: Optional[Dict[str, Any]] = None,
    lookback_days: int = 5,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Fetch candle data from Dhan HQ API v2.
    Returns: (candles, success)
    """
    if not credentials or not security_id:
        return [], False

    access_token = credentials.get("accessToken") or credentials.get("access_token")
    client_id = credentials.get("clientId") or credentials.get("client_id") or credentials.get("dhanClientId")

    if not access_token or not client_id:
        return [], False

    base_url = getattr(settings, "DHAN_API_BASE_URL", "https://api.dhan.co/v2").rstrip("/")
    if base_url.endswith("/v2"):
        intraday_url = f"{base_url}/charts/intraday"
        historical_url = f"{base_url}/charts/historical"
    else:
        intraday_url = f"{base_url}/v2/charts/intraday"
        historical_url = f"{base_url}/v2/charts/historical"

    headers = {
        "access-token": str(access_token).strip(),
        "client-id": str(client_id).strip(),
        "dhanClientId": str(client_id).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    now = datetime.now()
    from_date = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")
    to_date = now.strftime("%Y-%m-%d %H:%M:%S")
    interval = DHAN_INTERVAL_MAP.get(timeframe, "5")

    payload = {
        "securityId": str(security_id),
        "exchangeSegment": exchange_segment,
        "instrument": instrument,
    }

    # Try intraday endpoint if interval is minutes, else historical
    if interval in ["1", "5", "15", "25", "60"]:
        url = intraday_url
        payload.update({
            "interval": interval,
            "fromDate": from_date,
            "toDate": to_date,
        })
    else:
        url = historical_url
        payload.update({
            "expiryCode": 0,
            "fromDate": (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d"),
            "toDate": now.strftime("%Y-%m-%d"),
        })

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Dhan chart request failed [{resp.status_code}]: {resp.text[:200]}")
                return [], False

            data = resp.json()
            candles = _parse_dhan_response(data)
            if candles:
                logger.info(f"Fetched {len(candles)} candles from Dhan for security_id={security_id}")
                return candles, True
            return [], False
    except Exception as e:
        logger.warning(f"Error calling Dhan chart endpoint: {e}")
        return [], False


def _parse_dhan_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse Dhan charts array payload into canonical candle dicts."""
    candles: List[Dict[str, Any]] = []
    if not isinstance(data, dict):
        return candles

    opens = data.get("open") or []
    highs = data.get("high") or []
    lows = data.get("low") or []
    closes = data.get("close") or []
    volumes = data.get("volume") or []
    timestamps = data.get("start_Time") or data.get("timestamp") or []

    n = min(len(opens), len(highs), len(lows), len(closes))
    for i in range(n):
        ts_val = timestamps[i] if i < len(timestamps) else None
        dt = None
        if isinstance(ts_val, (int, float)):
            try:
                dt = datetime.fromtimestamp(ts_val, tz=timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)
        elif isinstance(ts_val, str):
            try:
                dt = datetime.fromisoformat(ts_val)
            except Exception:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        vol = float(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0.0

        candles.append({
            "timestamp": dt,
            "open": float(opens[i]),
            "high": float(highs[i]),
            "low": float(lows[i]),
            "close": float(closes[i]),
            "volume": vol,
        })

    return candles


def _fetch_yfinance_sync(ticker_symbol: str, interval: str, period: str) -> List[Dict[str, Any]]:
    """Run yfinance history in a worker thread."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return []

        candles: List[Dict[str, Any]] = []
        for index, row in df.iterrows():
            ts = index.to_pydatetime() if hasattr(index, "to_pydatetime") else index
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            candles.append({
                "timestamp": ts,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0.0)),
            })
        return candles
    except Exception as e:
        logger.warning(f"yfinance fetch error for {ticker_symbol}: {e}")
        return []


async def fetch_candles_yfinance(
    symbol: str,
    timeframe: str = "5m",
) -> Tuple[List[Dict[str, Any]], bool]:
    """Fetch candles via yfinance as reliable fallback."""
    ticker_str = get_yahoo_ticker(symbol)
    interval, period = YF_INTERVAL_MAP.get(timeframe, ("5m", "5d"))

    try:
        candles = await asyncio.to_thread(_fetch_yfinance_sync, ticker_str, interval, period)
        if candles:
            logger.info(f"Fetched {len(candles)} candles via yfinance for {ticker_str}")
            return candles, True
    except Exception as e:
        logger.warning(f"Error in async yfinance fetch: {e}")

    return [], False


def generate_synthetic_candles(symbol: str, count: int = 200, base_price: float = 24000.0) -> List[Dict[str, Any]]:
    """
    Safe deterministic candle generator for off-market / sandbox testing
    when no external live feed is reachable.
    """
    import math
    candles: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    curr_price = base_price

    for i in range(count, 0, -1):
        t = now - timedelta(minutes=i * 5)
        # Gentle sinusoidal variation with some noise
        drift = math.sin(i * 0.15) * (base_price * 0.003)
        open_p = curr_price + drift
        high_p = open_p + abs(math.cos(i * 0.2)) * (base_price * 0.002) + 2.0
        low_p = open_p - abs(math.sin(i * 0.3)) * (base_price * 0.002) - 2.0
        close_p = (open_p + high_p + low_p) / 3.0
        vol = 1000 + int(abs(math.sin(i * 0.5)) * 5000)

        curr_price = close_p
        candles.append({
            "timestamp": t,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": vol,
        })
    return candles


async def get_candles(
    symbol: str,
    timeframe: str = "5m",
    security_id: Optional[str] = None,
    exchange_segment: str = "NSE_EQ",
    credentials: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Unified candle retrieval:
    1. Try Dhan REST API (if credentials and security_id provided)
    2. Fall back to yfinance
    3. Fall back to synthetic data if completely unreachable

    Returns: (candles, data_source_str)
    """
    # 1. Try Dhan
    if credentials and security_id:
        try:
            dhan_candles, ok = await fetch_candles_dhan(
                security_id=security_id,
                exchange_segment=exchange_segment,
                timeframe=timeframe,
                credentials=credentials,
            )
            if ok and len(dhan_candles) >= 10:
                return dhan_candles, "DHAN"
        except Exception as e:
            logger.warning(f"Dhan fetch failed: {e}. Falling back to yfinance.")

    # 2. Try yfinance
    try:
        yf_candles, ok = await fetch_candles_yfinance(symbol=symbol, timeframe=timeframe)
        if ok and len(yf_candles) >= 10:
            return yf_candles, "YFINANCE"
    except Exception as e:
        logger.warning(f"yfinance fetch failed: {e}")

    # 3. Synthetic fallback (for test / offline resilience)
    logger.info(f"Using synthetic fallback candles for {symbol}")
    base_p = 24500.0 if "NIFTY" in symbol.upper() else 1500.0
    synth_candles = generate_synthetic_candles(symbol=symbol, count=100, base_price=base_p)
    return synth_candles, "FALLBACK_SYNTHETIC"
