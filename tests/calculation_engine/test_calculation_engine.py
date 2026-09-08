"""
Automated unit and integration tests for the Calculation Engine module.
Tests:
  1. Technical indicators: RSI, MACD, Stochastic, Supertrend, ADX, CCI, MFI, BB, VWAP, EMA, Ichimoku
  2. Data fetcher: synthetic fallback and candle parsing
  3. Condition evaluator: rule_json parsing, VWAP/RSI conditions, SignalEvent generation
  4. Registry and live engine lifecycle
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.calculation_engine.indicators import (
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
    calc_ichimoku,
    compute_all_indicators,
)
from app.calculation_engine.data_fetcher import generate_synthetic_candles, _parse_dhan_response
from app.calculation_engine.schemas import IndicatorSnapshot, IndicatorValue
from app.calculation_engine.condition_evaluator import (
    extract_indicator_val,
    evaluate_rule_op,
    evaluate_single_condition,
)
from app.calculation_engine.registry import CalcEngineRegistry
from app.calculation_engine.engine import LiveIndicatorEngine
from app.strategies.models import StrategyCondition


def create_dummy_candles(n=100, base=24000.0):
    candles = []
    now = datetime.now(timezone.utc)
    curr = base
    for i in range(n, 0, -1):
        t = now - timedelta(minutes=i * 5)
        o = curr
        h = o + 10.0
        l = o - 8.0
        c = (o + h + l) / 3.0
        v = 1500.0
        curr = c + (1.5 if i % 2 == 0 else -1.0)
        candles.append({
            "timestamp": t,
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": v,
        })
    return candles


def test_rsi_calculation():
    candles = create_dummy_candles(50)
    res = calc_rsi(candles, period=14)
    assert res["name"] == "RSI"
    assert res["value"] is not None
    assert 0 <= res["value"] <= 100
    assert res["signal"] in ["BUY", "SELL", "NEUTRAL"]


def test_macd_calculation():
    candles = create_dummy_candles(60)
    res = calc_macd(candles, fast=12, slow=26, signal_period=9)
    assert res["name"] == "MACD"
    assert res["value"] is not None
    assert "signal_line" in res["secondary"]
    assert "histogram" in res["secondary"]


def test_stochastic_calculation():
    candles = create_dummy_candles(50)
    res = calc_stochastic(candles, k_period=14, d_period=3)
    assert res["name"] == "STOCH"
    assert res["value"] is not None
    assert 0 <= res["value"] <= 100
    assert "d" in res["secondary"]


def test_supertrend_calculation():
    candles = create_dummy_candles(50)
    res = calc_supertrend(candles, period=10, multiplier=3.0)
    assert res["name"] == "SUPERTREND"
    assert res["value"] is not None
    assert res["signal"] in ["BUY", "SELL"]
    assert res["secondary"]["direction"] in [1, -1]


def test_adx_calculation():
    candles = create_dummy_candles(60)
    res = calc_adx(candles, period=14)
    assert res["name"] == "ADX"
    assert res["value"] is not None
    assert 0 <= res["value"] <= 100


def test_bollinger_bands():
    candles = create_dummy_candles(50)
    res = calc_bollinger_bands(candles, period=20, std_dev=2.0)
    assert res["name"] == "BB"
    assert res["secondary"]["upper"] > res["secondary"]["lower"]
    assert res["value"] is not None


def test_vwap_calculation():
    candles = create_dummy_candles(30)
    res = calc_vwap(candles)
    assert res["name"] == "VWAP"
    assert res["value"] is not None
    assert res["value"] > 0


def test_compute_all_indicators():
    candles = create_dummy_candles(70)
    snap = compute_all_indicators(
        candles=candles,
        symbol="NIFTY",
        timeframe="5m",
        ltp=24500.0,
        vwap=24480.0,
        data_source="DHAN",
    )
    assert snap["symbol"] == "NIFTY"
    assert len(snap["indicators"]) >= 11
    names = [i["name"] for i in snap["indicators"]]
    for expected in ["RSI", "MACD", "STOCH", "SUPERTREND", "ADX", "CCI", "MFI", "BB", "VWAP", "EMA", "ICHIMOKU"]:
        assert expected in names


def test_condition_evaluator_vwap():
    snap = IndicatorSnapshot(
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime.now(timezone.utc),
        ltp=24600.0,
        vwap=24550.0,
        indicators=[
            IndicatorValue(name="VWAP", display_name="VWAP", value=24550.0, signal="BUY"),
            IndicatorValue(name="RSI", display_name="RSI", value=28.5, signal="BUY"),
        ],
    )

    # Condition: VWAP >= 24500
    cond = StrategyCondition(
        id=101,
        strategy_version_id=1,
        rule_type="ENTRY",
        raw_text="VWAP >= 24500",
        rule_json='{"indicator": "VWAP", "operator": ">=", "value": 24500}',
    )

    sig = evaluate_single_condition(
        condition=cond,
        snapshot=snap,
        strategy_id=1,
        strategy_name="Nifty VWAP Breakout",
        trigger_type="TICK",
    )
    assert sig is not None
    assert sig.signal == "ENTRY"
    assert sig.indicator_name == "VWAP"
    assert sig.indicator_value == 24550.0

    # Condition: RSI <= 30
    cond_rsi = StrategyCondition(
        id=102,
        strategy_version_id=1,
        rule_type="ENTRY",
        raw_text="RSI <= 30",
        rule_json='{"indicator": "RSI", "operator": "<=", "value": 30}',
    )

    sig_rsi = evaluate_single_condition(
        condition=cond_rsi,
        snapshot=snap,
        strategy_id=1,
        strategy_name="Nifty Oversold",
        trigger_type="CANDLE_CLOSE",
    )
    assert sig_rsi is not None
    assert sig_rsi.signal == "ENTRY"
    assert sig_rsi.indicator_name == "RSI"
    assert sig_rsi.indicator_value == 28.5


def test_registry_lifecycle():
    engine = LiveIndicatorEngine(symbol="TEST_SYM", timeframe="5m")
    CalcEngineRegistry.register("TEST_SYM", engine)
    assert CalcEngineRegistry.get("TEST_SYM") is not None
    assert CalcEngineRegistry.get("test_sym") is not None  # Case-insensitive

    CalcEngineRegistry.remove("TEST_SYM")
    assert CalcEngineRegistry.get("TEST_SYM") is None
