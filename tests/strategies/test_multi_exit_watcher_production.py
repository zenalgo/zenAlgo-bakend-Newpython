"""
Production Unit & Integration Test Suite for Multi-Exit Watcher.
Validates:
1. Exact percentage-of-entry-price calculation for BUY and SELL positions.
2. Production test examples: Trade #3809, Trade #3802, Trade #3804, Entry 100.
3. Target trigger and Stop loss trigger thresholds.
4. Target progress % calculation with live PnL.
5. Market data freshness validation (rejects stale, negative, zero, and wrong instrument quotes).
6. IST (Asia/Kolkata) EOD cutoff verification.
7. Tick size normalization (0.05 paise rounding).
"""
import unittest
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytz

from app.strategies.exit_calculator import (
    calculate_exit_levels,
    extract_target_and_sl_config,
    validate_market_quote_freshness,
    round_to_tick,
    is_eod_cutoff_reached,
    ExitLevels
)

class TestMultiExitWatcherProduction(unittest.TestCase):

    def test_acceptance_criteria_1_entry_100(self):
        """Acceptance Criteria: Entry = 100, Target = +2%, SL = -1% for BUY position."""
        res = calculate_exit_levels(
            entry_price=100.0,
            quantity=50,
            current_ltp=100.0,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="BUY"
        )
        assert res.target_price == 102.0
        assert res.stop_loss_price == 99.0
        assert res.target_profit == 100.0   # (102.0 - 100.0) * 50
        assert res.max_risk == -50.0        # (99.0 - 100.0) * 50
        assert res.is_target_met is False
        assert res.is_sl_met is False
        assert res.progress_pct == 0.0

    def test_example_1_trade_3809(self):
        """Trade #3809: Entry = 127.76, Qty = 50, Target = 2%, SL = 1%, LTP = 142.42."""
        res = calculate_exit_levels(
            entry_price=127.76,
            quantity=50,
            current_ltp=142.42,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="BUY"
        )
        # 127.76 * 1.02 = 130.3152 -> 130.32
        assert res.target_price == 130.32
        # 127.76 * 0.99 = 126.4824 -> 126.48
        assert res.stop_loss_price == 126.48
        assert res.current_pnl == 733.0     # (142.42 - 127.76) * 50 = 14.66 * 50 = 733.0
        assert res.is_target_met is True    # 142.42 >= 130.32
        assert res.is_sl_met is False
        assert res.progress_pct == 100.0
        assert "TARGET PROFIT HIT" in (res.exit_reason or "")

    def test_example_2_trade_3802(self):
        """Trade #3802: Entry = 10.35, Qty = 250, Target = 2%, SL = 1%, LTP = 12.29."""
        res = calculate_exit_levels(
            entry_price=10.35,
            quantity=250,
            current_ltp=12.29,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="BUY"
        )
        # 10.35 * 1.02 = 10.557 -> 10.56
        assert res.target_price == 10.56
        # 10.35 * 0.99 = 10.2465 -> 10.25
        assert res.stop_loss_price == 10.25
        assert res.current_pnl == 485.0     # (12.29 - 10.35) * 250 = 1.94 * 250 = 485.0
        assert res.is_target_met is True    # 12.29 >= 10.56
        assert res.is_sl_met is False
        assert res.progress_pct == 100.0
        assert "TARGET PROFIT HIT" in (res.exit_reason or "")

    def test_example_3_trade_3804(self):
        """Trade #3804: Entry = 10.77, Qty = 250, Target = 2%, SL = 1%."""
        res = calculate_exit_levels(
            entry_price=10.77,
            quantity=250,
            current_ltp=10.77,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="BUY"
        )
        # 10.77 * 1.02 = 10.9854 -> 10.99
        assert res.target_price == 10.99
        # 10.77 * 0.99 = 10.6623 -> 10.66
        assert res.stop_loss_price == 10.66
        assert res.is_target_met is False
        assert res.is_sl_met is False

    def test_target_triggered(self):
        """Target Trigger: Entry = 100, Target = 102, Live LTP = 102.10 -> TARGET_TRIGGERED."""
        res = calculate_exit_levels(
            entry_price=100.0,
            quantity=50,
            current_ltp=102.10,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="BUY"
        )
        assert res.is_target_met is True
        assert res.is_sl_met is False
        assert res.progress_pct == 100.0

    def test_target_not_triggered_and_progress(self):
        """Target Not Triggered: Entry = 100, Target = 102, Live LTP = 101.00 -> 50% Progress."""
        res = calculate_exit_levels(
            entry_price=100.0,
            quantity=50,
            current_ltp=101.00,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="BUY"
        )
        assert res.is_target_met is False
        assert res.is_sl_met is False
        assert res.current_pnl == 50.0      # (101 - 100) * 50
        assert res.target_profit == 100.0   # (102 - 100) * 50
        assert res.progress_pct == 50.0     # 50 / 100 * 100 = 50.0%

    def test_stop_loss_triggered(self):
        """Stop Loss Triggered: Entry = 100, SL = 99, Live LTP = 98.90 -> SL_TRIGGERED."""
        res = calculate_exit_levels(
            entry_price=100.0,
            quantity=50,
            current_ltp=98.90,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="BUY"
        )
        assert res.is_target_met is False
        assert res.is_sl_met is True
        assert "STOP LOSS HIT" in (res.exit_reason or "")

    def test_sell_position_reversal(self):
        """SELL / SHORT position: Target is below entry, SL is above entry."""
        res = calculate_exit_levels(
            entry_price=100.0,
            quantity=50,
            current_ltp=98.00,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="SELL"
        )
        assert res.target_price == 98.0     # 100 * (1 - 0.02)
        assert res.stop_loss_price == 101.0 # 100 * (1 + 0.01)
        assert res.current_pnl == 100.0     # (100 - 98) * 50 = +100
        assert res.is_target_met is True

        # SL test for SHORT
        res_sl = calculate_exit_levels(
            entry_price=100.0,
            quantity=50,
            current_ltp=101.50,
            target_val=2.0,
            target_type="PERCENTAGE",
            sl_val=1.0,
            sl_type="PERCENTAGE",
            direction="SELL"
        )
        assert res_sl.is_sl_met is True

    def test_points_based_configuration(self):
        """Points mode: Target = 20 pts, SL = 10 pts."""
        res = calculate_exit_levels(
            entry_price=150.0,
            quantity=50,
            current_ltp=165.0,
            target_val=20.0,
            target_type="POINTS",
            sl_val=10.0,
            sl_type="POINTS",
            direction="BUY"
        )
        assert res.target_price == 170.0
        assert res.stop_loss_price == 140.0
        assert res.target_profit == 1000.0  # 20 * 50
        assert res.max_risk == -500.0       # -10 * 50
        assert res.current_pnl == 750.0     # (165 - 150) * 50
        assert res.progress_pct == 75.0     # 750 / 1000 = 75%

    def test_market_data_freshness_validation(self):
        """Rejects stale quotes, zero/negative prices, and mismatched instruments."""
        now = datetime.now(timezone.utc)
        
        # 1. Valid quote
        valid_quote = {
            "symbol": "NIFTY 23850 CE",
            "currentLtp": 130.85,
            "timestamp": now.timestamp()
        }
        is_fresh, msg = validate_market_quote_freshness(valid_quote, expected_symbol="NIFTY 23850 CE", max_age_seconds=60.0)
        assert is_fresh is True
        assert msg == "VALID"

        # 2. Stale quote (age = 120s)
        stale_quote = {
            "symbol": "NIFTY 23850 CE",
            "currentLtp": 130.85,
            "timestamp": (now - timedelta(seconds=120)).timestamp()
        }
        is_fresh, msg = validate_market_quote_freshness(stale_quote, expected_symbol="NIFTY 23850 CE", max_age_seconds=60.0)
        assert is_fresh is False
        assert "Stale market data tick" in msg

        # 3. Wrong instrument quote (NIFTY 23800 PE instead of NIFTY 23850 CE)
        mismatch_quote = {
            "symbol": "NIFTY 23800 PE",
            "currentLtp": 95.0,
            "timestamp": now.timestamp()
        }
        is_fresh, msg = validate_market_quote_freshness(mismatch_quote, expected_symbol="NIFTY 23850 CE", max_age_seconds=60.0)
        assert is_fresh is False
        assert "Instrument mismatch" in msg

        # 4. Zero or Negative LTP
        invalid_quote = {
            "symbol": "NIFTY 23850 CE",
            "currentLtp": 0.0,
            "timestamp": now.timestamp()
        }
        is_fresh, msg = validate_market_quote_freshness(invalid_quote, expected_symbol=None)
        assert is_fresh is False
        assert "Non-positive or invalid LTP" in msg

    def test_eod_cutoff_ist_evaluation(self):
        """Validates EOD 15:15 IST evaluation using Asia/Kolkata."""
        kolkata_tz = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(kolkata_tz)
        
        # Test function executes cleanly without exceptions
        eod_status = is_eod_cutoff_reached("15:15")
        if now_ist.hour > 15 or (now_ist.hour == 15 and now_ist.minute >= 15):
            assert eod_status is True
        else:
            assert eod_status is False

    def test_round_to_tick_precision(self):
        """Validates NSE 0.05 paise tick size rounding."""
        assert round_to_tick(10.557, 0.05) == 10.55
        assert round_to_tick(10.578, 0.05) == 10.60
        assert round_to_tick(100.01, 0.05) == 100.00
        assert round_to_tick(100.04, 0.05) == 100.05
