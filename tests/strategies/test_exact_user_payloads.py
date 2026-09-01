import pytest
from datetime import date
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.future import select

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.core.security import create_access_token
from app.brokers.models import BrokerAccount
from app.strategies.models import Strategy, StrategyExecution
from app.strategies.service import StrategyService
from app.strategies.state_manager import strategy_state_manager
from app.strategies.enums import StrategyLifecycleState
from app.strategies.payload_normalizer import FrontendPayloadNormalizer
from app.execution.contracts import ExecutionRequest
from app.execution.enums import ExecutionMode
from app.execution.engine import ExecutionEngine
from app.execution.models import StrategySignal, StrategyUserExecutionTrace, StrategyExecutionBatch

PAYLOAD_1 = {
  "schemaVersion": "2.0.0",
  "meta": {
    "strategyId": "EMA_8_33_PULLBACK",
    "strategyName": "8/33 EMA Pullback",
    "authorName": "Ankur"
  },
  "description": "Intraday trend-following strategy using 8 EMA and 33 EMA.",
  "coreIdea": "Trade in the direction of the EMA trend after price pulls back toward the 33 EMA and gives confirmation.",
  "category": "Option Buying - Index",
  "marketBias": "NEUTRAL",
  "strategyStyle": "Trend Following",
  "tradingHorizon": "Intraday",
  "timeframe": "5m",
  "instrument": {
    "type": "Options",
    "underlying": "NIFTY 50",
    "indicesArray": ["NIFTY 50"],
    "expiryType": "Weekly"
  },
  "schedule": {
    "entryFrom": "09:30",
    "entryTo": "14:30",
    "forcedExitTime": "15:15",
    "entryTimeMode": "Time Window",
    "exitTimeMode": "End of Session",
    "maxHoldingPeriod": "Same Day"
  },
  "entryConditions": [
    "EMA 8 is above EMA 33 for bullish setup",
    "EMA 8 is below EMA 33 for bearish setup",
    "Price pulls back toward EMA 33",
    "Strong bullish candle confirmation for CALL",
    "Strong bearish candle confirmation for PUT",
    "CALL entry when confirmation candle high breaks",
    "PUT entry when confirmation candle low breaks"
  ],
  "entry": {
    "logic": "ALL (AND)",
    "timeframeMode": "Same as Entry Timeframe",
    "secondaryTimeframe": "",
    "marketFilters": [
      "Avoid first 15 minutes",
      "Avoid highly volatile conditions"
    ]
  },
  "exitConditions": [
    "Stop loss is hit",
    "Target of 2R is hit",
    "EMA 8 crosses to the opposite side of EMA 33",
    "Forced exit at 15:15"
  ],
  "exit": {
    "logic": "ANY (OR)",
    "partialExit": {
      "enabled": True,
      "plan": "Book 50% at 1R and trail remaining 50% using EMA 8"
    },
    "trailingStop": {
      "enabled": True,
      "rule": "Trail after 1R using EMA 8"
    }
  },
  "keyRememberPoints": [
    "Use 5-minute NIFTY chart",
    "EMA 8 is the fast EMA",
    "EMA 33 is the slow EMA",
    "Trade in the direction of the EMA trend",
    "Wait for a pullback",
    "Do not chase extended candles",
    "Enter only after confirmation candle breakout"
  ],
  "riskManagement": {
    "riskRewardRatio": "1:2",
    "stopLoss": "Below confirmation candle low for CALL / above confirmation candle high for PUT",
    "maxLossPerTrade": "₹2500",
    "maxLossPerDay": "₹5000",
    "maxLossPerWeek": "₹15000",
    "maxTradesPerDay": "3",
    "maxOpenPositions": "1",
    "consecutiveLossLimit": "3",
    "cooldownMinutes": "15",
    "positionSizingMode": "Risk Based",
    "afterLossAction": "Reduce Size",
    "capitalAllocationPerTrade": "5%"
  },
  "options": {
    "optionType": "Auto",
    "strikeSelection": "ATM",
    "strikeOffset": "0",
    "expiry": "Current Weekly",
    "legs": []
  },
  "execution": {
    "orderType": "Market",
    "triggerType": "Break Confirmation Candle",
    "slippage": "0.10%",
    "orderTimeout": "30",
    "reentry": {
      "mode": "After New Setup",
      "maxReentries": "1"
    }
  },
  "target": {
    "value": "2R",
    "scaleOutPlan": "Book 50% at 1R and trail remaining 50% using EMA 8"
  }
}

PAYLOAD_2 = {
  "schemaVersion": "2.0.0",
  "meta": {
    "strategyId": "RSI_60_ALERT_CANDLE",
    "strategyName": "NIFTY RSI 60 Alert Candle",
    "authorName": "Ankur"
  },
  "description": "Intraday NIFTY options buying strategy using RSI 60 momentum confirmation and alert-candle breakout.",
  "coreIdea": "When RSI crosses above 60, mark the alert candle and buy CE when its high breaks. For bearish conditions, use the opposite setup for PE.",
  "category": "Option Buying - Index",
  "marketBias": "NEUTRAL",
  "strategyStyle": "Momentum",
  "tradingHorizon": "Intraday",
  "timeframe": "15m",
  "instrument": {
    "type": "Options",
    "underlying": "NIFTY 50",
    "indicesArray": ["NIFTY 50"],
    "expiryType": "Weekly"
  },
  "schedule": {
    "entryFrom": "09:30",
    "entryTo": "14:30",
    "forcedExitTime": "15:15",
    "entryTimeMode": "Time Window",
    "exitTimeMode": "End of Session",
    "maxHoldingPeriod": "Same Day"
  },
  "entryConditions": [
    "RSI crosses above 60 for bullish setup",
    "Mark the candle responsible for the RSI 60 breakout as the alert candle",
    "Wait for alert candle high to break",
    "Buy CE on break of alert candle high",
    "RSI crosses below bearish threshold for bearish setup",
    "Mark the bearish alert candle",
    "Buy PE on break of alert candle low"
  ],
  "entry": {
    "logic": "ALL (AND)",
    "timeframeMode": "Same as Entry Timeframe",
    "secondaryTimeframe": "",
    "marketFilters": [
      "Avoid first 15 minutes",
      "Avoid highly volatile conditions"
    ]
  },
  "exitConditions": [
    "Stop loss is hit",
    "Alert candle range target is hit",
    "Forced exit at 15:15"
  ],
  "exit": {
    "logic": "ANY (OR)",
    "partialExit": {
      "enabled": True,
      "plan": "Book partial profit at first target and trail remaining position"
    },
    "trailingStop": {
      "enabled": True,
      "rule": "Trail after first target"
    }
  },
  "keyRememberPoints": [
    "Use 15-minute NIFTY chart",
    "RSI is used as the momentum trigger",
    "Bullish RSI trigger is above 60",
    "Use the alert candle created by the RSI trigger",
    "Do not enter immediately on RSI crossover",
    "Wait for alert candle breakout",
    "Use CE for bullish breakout",
    "Use PE for bearish breakout"
  ],
  "riskManagement": {
    "riskRewardRatio": "1:2",
    "stopLoss": "Alert candle low for CE / alert candle high for PE",
    "maxLossPerTrade": "₹2500",
    "maxLossPerDay": "₹5000",
    "maxLossPerWeek": "₹15000",
    "maxTradesPerDay": "3",
    "maxOpenPositions": "1",
    "consecutiveLossLimit": "3",
    "cooldownMinutes": "15",
    "positionSizingMode": "Risk Based",
    "afterLossAction": "Reduce Size",
    "capitalAllocationPerTrade": "5%"
  },
  "options": {
    "optionType": "Auto",
    "strikeSelection": "ATM",
    "strikeOffset": "0",
    "expiry": "Current Weekly",
    "legs": []
  },
  "execution": {
    "orderType": "Market",
    "triggerType": "Break Alert Candle",
    "slippage": "0.10%",
    "orderTimeout": "30",
    "reentry": {
      "mode": "After New Setup",
      "maxReentries": "1"
    }
  },
  "target": {
    "value": "Alert Candle Range",
    "scaleOutPlan": "Partial profit followed by trailing stop"
  }
}

PAYLOAD_3 = {
  "schemaVersion": "2.0.0",
  "meta": {
    "strategyId": "RELIANCE_S3_R3_PIVOT_REVERSAL",
    "strategyName": "Reliance S3/R3 Pivot Reversal",
    "authorName": "Ankur"
  },
  "description": "Monthly Camarilla pivot reversal strategy for Reliance using R3 and S3 with mandatory 200-point option hedging.",
  "coreIdea": "Monitor Monthly Camarilla R3 and S3 levels. Sell CE after a fake breakout or bearish reversal at R3 and sell PE after a fake breakdown or bullish reversal at S3. Always hedge the short option approximately 200 points away.",
  "category": "Option Selling - Stock",
  "marketBias": "NEUTRAL",
  "strategyStyle": "Mean Reversion",
  "tradingHorizon": "Monthly",
  "timeframe": "Daily",
  "instrument": {
    "type": "Options",
    "underlying": "RELIANCE",
    "indicesArray": ["RELIANCE"],
    "expiryType": "Monthly"
  },
  "pivotConfiguration": {
    "indicator": "Pivot Points Standard",
    "timeframe": "Daily",
    "periodicity": "Monthly",
    "calculation": "Camarilla",
    "levels": [
      "S3",
      "R3"
    ]
  },
  "schedule": {
    "entryFrom": "",
    "entryTo": "",
    "forcedExitTime": "",
    "entryTimeMode": "Signal Based",
    "exitTimeMode": "Expiry / Target Based",
    "maxHoldingPeriod": "Until Monthly Expiry",
    "eventExclusion": {
      "enabled": True,
      "eventType": "QUARTERLY_EARNINGS",
      "rule": "Avoid trading during months when Reliance has quarterly earnings results."
    }
  },
  "entryConditions": [
    "Monitor Monthly Camarilla R3 and S3",
    "R3 setup: Reliance touches R3",
    "Price moves above R3",
    "Price fails to sustain above R3",
    "Price closes back below R3",
    "OR bearish reversal candlestick pattern forms at R3",
    "Sell CE after bearish confirmation at R3",
    "Buy CE hedge approximately 200 points away",
    "S3 setup: Reliance drops to S3",
    "Price moves below S3",
    "Price fails to sustain below S3",
    "Price closes back above S3",
    "Sell PE after bullish confirmation at S3",
    "Buy PE hedge approximately 200 points away"
  ],
  "entry": {
    "logic": "ALL (AND)",
    "timeframeMode": "Signal Based",
    "secondaryTimeframe": "",
    "marketFilters": [
      "Do not trade during quarterly earnings-result months",
      "Do not sell CE on a clean breakout above R3",
      "Do not sell PE on a clean breakdown below S3"
    ]
  },
  "exitConditions": [
    "Target profit of approximately 2% to 3% is achieved",
    "Monthly expiry is approaching",
    "Defined risk limit is reached",
    "Exit short option and corresponding hedge together"
  ],
  "exit": {
    "logic": "ANY (OR)",
    "partialExit": {
      "enabled": False,
      "plan": ""
    },
    "trailingStop": {
      "enabled": False,
      "rule": ""
    }
  },
  "keyRememberPoints": [
    "Underlying is RELIANCE",
    "Use Pivot Points Standard",
    "Pivot calculation is Camarilla",
    "Pivot timeframe is Daily",
    "Pivot periodicity is Monthly",
    "Only R3 and S3 are monitored",
    "R3 is the CE-selling zone",
    "S3 is the PE-selling zone",
    "Wait for rejection rather than blindly selling at the level",
    "Fake breakout requires price above R3 followed by close below R3",
    "Fake breakdown requires price below S3 followed by close above S3",
    "Always hedge the short option",
    "Hedge approximately 200 points away",
    "Primary objective is theta decay",
    "Avoid quarterly earnings months"
  ],
  "riskManagement": {
    "riskRewardRatio": "",
    "stopLoss": "Strategy invalidation above R3 for CE setup / below S3 for PE setup",
    "maxLossPerTrade": "",
    "maxLossPerDay": "",
    "maxLossPerWeek": "",
    "maxTradesPerDay": "1",
    "maxOpenPositions": "1",
    "consecutiveLossLimit": "2",
    "cooldownMinutes": "0",
    "positionSizingMode": "Fixed Lots",
    "afterLossAction": "Stop Strategy",
    "capitalAllocationPerTrade": ""
  },
  "options": {
    "optionType": "Both",
    "strikeSelection": "Custom",
    "strikeOffset": "200",
    "expiry": "Current Monthly",
    "legs": [
      {
        "legId": 1,
        "action": "SELL",
        "optionType": "CE",
        "strike": "Selected OTM CE",
        "expiry": "Current Monthly",
        "quantity": "1",
        "role": "Short CE"
      },
      {
        "legId": 2,
        "action": "BUY",
        "optionType": "CE",
        "strike": "Short CE strike + 200 points",
        "expiry": "Current Monthly",
        "quantity": "1",
        "role": "CE Hedge"
      },
      {
        "legId": 3,
        "action": "SELL",
        "optionType": "PE",
        "strike": "Selected OTM PE",
        "expiry": "Current Monthly",
        "quantity": "1",
        "role": "Short PE"
      },
      {
        "legId": 4,
        "action": "BUY",
        "optionType": "PE",
        "strike": "Short PE strike - 200 points",
        "expiry": "Current Monthly",
        "quantity": "1",
        "role": "PE Hedge"
      }
    ]
  },
  "execution": {
    "orderType": "Limit",
    "triggerType": "Fake Breakout / Fake Breakdown Confirmation",
    "slippage": "0.20%",
    "orderTimeout": "30",
    "reentry": {
      "mode": "After New Setup",
      "maxReentries": "0"
    }
  },
  "target": {
    "value": "2% - 3%",
    "scaleOutPlan": "Exit full strategy position when target is achieved or monthly expiry approaches"
  }
}

@pytest.fixture
async def auth_client(client, db_session):
    user = User(
        email="ankur@zenalgo.com",
        password_hash=hash_password("devpass123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-ANK-01"
    )
    db_session.add(user)
    await db_session.flush()

    broker = BrokerAccount(user_id=user.id, broker_code="MOCK", account_client_id="MOCK-ANK-01", status="ACTIVE")
    db_session.add(broker)
    await db_session.flush()

    token = create_access_token(user.email, user.role.value, ["ACCOUNT_READ", "TRADE_READ", "TRADE_EXECUTE"])
    client.headers["Authorization"] = f"Bearer {token}"
    return client, user

@pytest.mark.asyncio
async def test_exact_strategy_1_creation_and_retrieval(auth_client):
    client, user = auth_client
    res = await client.post("/api/strategy", json=PAYLOAD_1)
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["id"] is not None

    get_res = await client.get(f"/api/strategy/{data['id']}")
    assert get_res.status_code == 200
    retrieved = get_res.json()["data"]
    assert retrieved["name"] == "8/33 EMA Pullback"
    assert retrieved["timeframe"] == "5m"
    assert retrieved["tradingHorizon"] == "Intraday"

@pytest.mark.asyncio
async def test_exact_strategy_2_creation_and_retrieval(auth_client):
    client, user = auth_client
    res = await client.post("/api/strategy", json=PAYLOAD_2)
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["id"] is not None

    get_res = await client.get(f"/api/strategy/{data['id']}")
    assert get_res.status_code == 200
    retrieved = get_res.json()["data"]
    assert retrieved["name"] == "NIFTY RSI 60 Alert Candle"
    assert retrieved["timeframe"] == "15m"

@pytest.mark.asyncio
async def test_exact_strategy_3_creation_and_retrieval(auth_client):
    client, user = auth_client
    res = await client.post("/api/strategy", json=PAYLOAD_3)
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["id"] is not None

    get_res = await client.get(f"/api/strategy/{data['id']}")
    assert get_res.status_code == 200
    retrieved = get_res.json()["data"]
    assert retrieved["name"] == "Reliance S3/R3 Pivot Reversal"
    assert retrieved["underlying"] == "RELIANCE"
    assert retrieved["timeframe"] == "Daily"
    assert retrieved["tradingHorizon"] == "Monthly"
    assert len(retrieved["options"]["legs"]) == 4

@pytest.mark.asyncio
async def test_exact_payloads_activation_and_execution(auth_client, db_session):
    client, user = auth_client
    
    # 1. Create Strategy 1
    res1 = await client.post("/api/strategy", json=PAYLOAD_1)
    strat1_id = res1.json()["data"]["id"]
    version1_id = res1.json()["data"]["currentVersionId"]

    # Activate Strategy 1
    act_res = await client.post(f"/api/strategy/{strat1_id}/activate")
    assert act_res.status_code == 200

    r_state = await strategy_state_manager.get_runtime_state(db_session, strat1_id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

    # Execute Paper Trade for Strategy 1
    sig1 = StrategySignal(strategy_id=strat1_id, strategy_version_id=version1_id, trading_date=date.today(), entry_time="09:35", signal_key=f"SIG-EXACT-S1-{strat1_id}", signal_type="ENTRY", direction="BUY", status="CREATED")
    db_session.add(sig1)
    await db_session.flush()

    batch1 = StrategyExecutionBatch(signal_id=sig1.id, strategy_id=strat1_id, strategy_version_id=version1_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch1)
    await db_session.flush()

    trace1 = StrategyUserExecutionTrace(execution_batch_id=batch1.id, signal_id=sig1.id, user_id=user.id, strategy_id=strat1_id, strategy_version_id=version1_id, correlation_id=f"TRACE-EXACT-S1-{sig1.id}", status="PENDING")
    db_session.add(trace1)
    await db_session.flush()

    exec_req1 = FrontendPayloadNormalizer.build_execution_request_from_signal(payload=PAYLOAD_1, user_id=user.id, strategy_id=strat1_id, strategy_version_id=version1_id, signal_id=sig1.id, execution_mode=ExecutionMode.PAPER)
    exec_res1 = await ExecutionEngine.execute(db_session, exec_req1)
    assert exec_res1.status.value == "FILLED"

    r_state_after = await strategy_state_manager.get_runtime_state(db_session, strat1_id)
    assert r_state_after.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

    # 2. Create Strategy 3 (Four-Leg Camarilla)
    res3 = await client.post("/api/strategy", json=PAYLOAD_3)
    strat3_id = res3.json()["data"]["id"]
    version3_id = res3.json()["data"]["currentVersionId"]

    act3_res = await client.post(f"/api/strategy/{strat3_id}/activate")
    assert act3_res.status_code == 200

    sig3 = StrategySignal(strategy_id=strat3_id, strategy_version_id=version3_id, trading_date=date.today(), entry_time="09:30", signal_key=f"SIG-EXACT-S3-{strat3_id}", signal_type="ENTRY", direction="BUY", status="CREATED")
    db_session.add(sig3)
    await db_session.flush()

    batch3 = StrategyExecutionBatch(signal_id=sig3.id, strategy_id=strat3_id, strategy_version_id=version3_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch3)
    await db_session.flush()

    trace3 = StrategyUserExecutionTrace(execution_batch_id=batch3.id, signal_id=sig3.id, user_id=user.id, strategy_id=strat3_id, strategy_version_id=version3_id, correlation_id=f"TRACE-EXACT-S3-{sig3.id}", status="PENDING")
    db_session.add(trace3)
    await db_session.flush()

    exec_req3 = FrontendPayloadNormalizer.build_execution_request_from_signal(payload=PAYLOAD_3, user_id=user.id, strategy_id=strat3_id, strategy_version_id=version3_id, signal_id=sig3.id, execution_mode=ExecutionMode.PAPER)
    assert len(exec_req3.legs) == 4

    exec_res3 = await ExecutionEngine.execute(db_session, exec_req3)
    assert exec_res3.status.value == "FILLED"
    assert len(exec_res3.leg_results) == 4
