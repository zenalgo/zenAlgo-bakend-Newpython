import pytest
from decimal import Decimal
from pydantic import ValidationError
from unittest.mock import patch

from app.execution.enums import (
    ExecutionStatus,
    ExecutionMode,
    OrderType,
    LegRole,
    OptionStrikePolicy,
    OptionExpiryPolicy
)
from app.execution.contracts import (
    LogicalLeg,
    ResolvedLeg,
    ExecutionRequest,
    ExecutionLegResult,
    ExecutionResult
)
from app.strategies.payload_normalizer import FrontendPayloadNormalizer

# Sample Strategy 1 Payload (Schema v2.0.0)
STRATEGY_1_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "meta": {"strategyId": "EMA_8_33_PULLBACK", "name": "EMA Pullback Strategy"},
    "instrument": {"underlying": "NIFTY", "expiryType": "CURRENT_WEEKLY"},
    "timeframe": "5m",
    "options": {"strikeSelection": "ATM", "optionType": "CE"},
    "execution": {"orderType": "MARKET", "slippage": "0.5", "orderTimeout": 30},
    "riskManagement": {"maxLossPerDay": "5000.00", "maxTradesPerDay": 3}
}

# Sample Strategy 2 Payload (Schema v2.0.0)
STRATEGY_2_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "meta": {"strategyId": "RSI_60_ALERT_CANDLE", "name": "RSI Alert Strategy"},
    "instrument": {"underlying": "NIFTY", "expiryType": "CURRENT_WEEKLY"},
    "timeframe": "15m",
    "options": {"strikeSelection": "ATM", "optionType": "CE"},
    "execution": {"orderType": "MARKET", "slippage": "0.5", "orderTimeout": 30},
    "riskManagement": {"maxLossPerDay": "5000.00", "maxTradesPerDay": 3}
}

# Sample Strategy 3 Payload (Multi-leg Option Selling with Hedge)
STRATEGY_3_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "meta": {"strategyId": "RELIANCE_S3_R3_PIVOT_REVERSAL", "name": "Reliance Pivot Reversal"},
    "instrument": {"underlying": "RELIANCE", "expiryType": "CURRENT_MONTHLY"},
    "timeframe": "Daily",
    "options": {
        "legs": [
            {
                "legId": 1,
                "sequence": 1,
                "role": "HEDGE",
                "side": "BUY",
                "optionType": "CE",
                "strikeSelection": "OTM",
                "strikeOffset": "200.0",
                "expiry": "CURRENT_MONTHLY",
                "lots": 1
            },
            {
                "legId": 2,
                "sequence": 2,
                "role": "SHORT",
                "side": "SELL",
                "optionType": "CE",
                "strikeSelection": "OTM",
                "strikeOffset": "0.0",
                "expiry": "CURRENT_MONTHLY",
                "lots": 1
            }
        ]
    },
    "execution": {"orderType": "MARKET", "slippage": "1.0", "orderTimeout": 60}
}

# --- 1. Frontend Payload Normalization Tests ---

def test_normalize_strategy_1_payload():
    """Validates single-leg normalization for Strategy 1."""
    req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=101,
        strategy_id=1,
        strategy_version_id=1,
        signal_id=5001,
        direction="BUY",
        approved_lots=2,
        required_capital=Decimal("45000.00")
    )
    assert req.underlying == "NIFTY"
    assert req.approved_lots == 2
    assert len(req.legs) == 1
    leg = req.legs[0]
    assert leg.role == LegRole.PRIMARY
    assert leg.side == "BUY"
    assert leg.option_type == "CE"
    assert leg.strike_policy == OptionStrikePolicy.ATM
    assert leg.expiry_policy == OptionExpiryPolicy.CURRENT_WEEKLY
    assert leg.lots == 2

def test_normalize_strategy_2_payload_sell_direction():
    """Validates single-leg PE normalization when direction is SELL."""
    req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_2_PAYLOAD,
        user_id=102,
        strategy_id=2,
        strategy_version_id=1,
        signal_id=5002,
        direction="SELL",
        approved_lots=1
    )
    assert req.underlying == "NIFTY"
    assert len(req.legs) == 1
    assert req.legs[0].option_type == "PE"

def test_normalize_strategy_3_multi_leg_payload():
    """Validates multi-leg hedge + short normalization for Strategy 3."""
    req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_3_PAYLOAD,
        user_id=103,
        strategy_id=3,
        strategy_version_id=1,
        signal_id=5003,
        direction="SELL",
        approved_lots=1,
        required_capital=Decimal("120000.00")
    )
    assert req.underlying == "RELIANCE"
    assert len(req.legs) == 2
    # Leg 1 is HEDGE (BUY)
    assert req.legs[0].role == LegRole.HEDGE
    assert req.legs[0].side == "BUY"
    assert req.legs[0].strike_offset == Decimal("200.0")
    assert req.legs[0].expiry_policy == OptionExpiryPolicy.CURRENT_MONTHLY
    # Leg 2 is SHORT (SELL)
    assert req.legs[1].role == LegRole.PRIMARY
    assert req.legs[1].side == "SELL"

# --- 2. Logical vs Resolved Leg Contract Tests ---

def test_logical_vs_resolved_leg_separation():
    """Proves logical instructions do not contain fake broker security IDs."""
    logical = LogicalLeg(
        leg_id=1,
        sequence=1,
        role=LegRole.PRIMARY,
        side="BUY",
        option_type="CE",
        strike_policy=OptionStrikePolicy.ATM,
        expiry_policy=OptionExpiryPolicy.CURRENT_WEEKLY,
        lots=1
    )
    assert logical.strike_policy == OptionStrikePolicy.ATM
    # Does not have security_id (resolution is strictly Step 10D)
    assert not hasattr(logical, "security_id")

    resolved = ResolvedLeg(
        leg_id=1,
        sequence=1,
        role=LegRole.PRIMARY,
        trading_symbol="NIFTY_25000_CE",
        security_id="SEC_NIFTY_25000_CE",
        side="BUY",
        quantity=50,
        lot_size=50,
        lots=1,
        price=Decimal("120.50")
    )
    assert resolved.security_id == "SEC_NIFTY_25000_CE"
    assert resolved.price == Decimal("120.50")

# --- 3. Validation and Decimal Precision Tests ---

def test_execution_request_empty_legs_raises_validation_error():
    with pytest.raises(ValidationError):
        ExecutionRequest(
            user_id=1,
            strategy_id=1,
            strategy_version_id=1,
            signal_id=1,
            underlying="NIFTY",
            correlation_id="CID-123",
            legs=[] # Empty legs invalid
        )

def test_logical_leg_zero_lots_raises_validation_error():
    with pytest.raises(ValidationError):
        LogicalLeg(
            leg_id=1,
            side="BUY",
            lots=0 # Zero lots invalid
        )

def test_exit_execution_request_support():
    """Validates that EXIT execution requests are cleanly supported."""
    req = ExecutionRequest(
        user_id=1,
        strategy_id=1,
        strategy_version_id=1,
        signal_id=999,
        signal_type="EXIT",
        direction="SELL",
        underlying="NIFTY",
        correlation_id="EXIT-CID-123",
        legs=[
            LogicalLeg(
                leg_id=1,
                role=LegRole.EXIT,
                side="SELL",
                option_type="CE",
                strike_policy=OptionStrikePolicy.ATM,
                lots=1
            )
        ]
    )
    assert req.signal_type == "EXIT"
    assert req.legs[0].role == LegRole.EXIT

def test_no_broker_calls_during_domain_construction():
    """Asserts that domain construction makes ZERO broker calls."""
    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_call:
        req = FrontendPayloadNormalizer.build_execution_request_from_signal(
            payload=STRATEGY_1_PAYLOAD,
            user_id=1,
            strategy_id=1,
            strategy_version_id=1,
            signal_id=10
        )
        assert req.user_id == 1
        mock_call.assert_not_called()
