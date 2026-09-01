# ZenAlgo Strategy API & Admin Tracing Reference Manual

**Schema Version:** `2.0.0`  
**Execution Environment:** `PAPER` (Enforced default, Live mode protected)  
**Target Audience:** Frontend Developers, Backend Engineers, QA, and System Administrators  
**Generated PDF Location:** [zenalgo_strategy_api_and_admin_tracing_docs.pdf](file:///Users/apple/.gemini/antigravity-ide/brain/4babdaee-ff45-4d48-be92-7ce7f90a0bf1/zenalgo_strategy_api_and_admin_tracing_docs.pdf)

---

## 1. Executive Summary & Architecture

The ZenAlgo Platform enables users to build, backtest, activate, and trade algorithmic strategies through a unified JSON Contract (`Schema 2.0.0`).

### End-to-End Execution Flow

```
[ Frontend Builder ] ---(POST /api/strategy)---> [ Strategy Service ]
                                                        |
                                            (Dual Persistence: Relational + JSON)
                                                        |
                                          [ POST .../activate ]
                                                        |
                                            (State: MONITORING_ENTRY)
                                                        |
[ Live Market Candle ] ---> [ Strategy Router ] ---> [ Golden Rule Engine ]
                                                                | (Condition Met)
                                                      [ Signal Engine ] (SIG-ENTRY-*)
                                                                |
                                                      [ Risk Engine ] (Trade Caps / Max Loss)
                                                                | (Approved)
                                                      [ Execution Validator ] (Hedge Check)
                                                                |
                                                      [ Execution Engine ] (PAPER / Mock)
                                                                | (Filled)
                                                      [ Position Manager ] (OPEN)
                                                                |
[ Live Market Updates ] ---> [ Exit Engine ] (Target 2R, SL, 15:15 Square-off)
                                      | (Triggered)
                             [ Exit Order Dispatched ] ---> [ Position CLOSED ]
```

---

## 2. Strategy Lifecycle & State Machine

Every strategy is tracked through deterministic states managed by `StrategyStateManager`:

| State | Description | Allowed Next Transitions |
| :--- | :--- | :--- |
| `WAITING` | Initial idle state after creation. No tick evaluation. | `ELIGIBLE`, `ARCHIVED` |
| `ELIGIBLE` | Ready for activation and schedule checks. | `MONITORING_ENTRY`, `PAUSED`, `WAITING` |
| `MONITORING_ENTRY` | Actively subscribed to market feed; evaluating entry conditions. | `ENTRY_SIGNAL`, `PAUSED`, `ELIGIBLE` |
| `ENTRY_SIGNAL` | Entry rule matched; emitted to Risk Engine. | `ORDER_PENDING`, `MONITORING_ENTRY` |
| `ORDER_PENDING` | Risk approved; order dispatched to Paper Broker. | `POSITION_OPEN`, `MONITORING_ENTRY` |
| `POSITION_OPEN` | Order filled; active position tracked in DB. | `MONITORING_EXIT`, `EXIT_ORDER_PENDING` |
| `MONITORING_EXIT` | ExitEngine evaluating Target, SL hit, Trailing Stop, or 15:15. | `EXIT_SIGNAL`, `EXIT_ORDER_PENDING` |
| `EXIT_SIGNAL` | Exit rule triggered; exit signal generated. | `EXIT_ORDER_PENDING`, `POSITION_OPEN` |
| `EXIT_ORDER_PENDING` | Square-off order executing at broker. | `POSITION_CLOSED`, `POSITION_OPEN` |
| `POSITION_CLOSED` | All legs closed and reconciled. | `MONITORING_ENTRY`, `ELIGIBLE`, `WAITING` |
| `PAUSED` / `ARCHIVED` | Manually paused or deleted; detached from market feed. | `ELIGIBLE`, `WAITING`, `MONITORING_ENTRY` |

---

## 3. Strategy APIs for Frontend Developers

---

### Endpoint 1: Create Strategy (Canonical)
- **HTTP Method:** `POST`
- **Route:** `/api/strategy` *(or `/api/v1/strategies`)*
- **Auth:** `Bearer <JWT_TOKEN>`
- **Content-Type:** `application/json`

#### Why We Use This API
This endpoint is used by the frontend Strategy Builder when the user clicks "Save Strategy". It accepts the rich Schema 2.0.0 JSON payload, validates all fields, creates the `Strategy` root entity, creates immutable `StrategyVersion` v1, parses logical legs into relational tables, preserves all builder configurations in `parameters` JSON, and initializes the runtime state machine in `WAITING` status.

#### Request Schema & Field Reference
| Field | Type | Required | Allowed Options / Format | Description |
| :--- | :--- | :---: | :--- | :--- |
| `schemaVersion` | `string` | **Yes** | `"2.0.0"` | Must match Schema 2.0.0. |
| `meta.strategyId` | `string` | **Yes** | Alphanumeric / Underscore | Human-readable identifier (e.g. `"EMA_8_33_PULLBACK"`). |
| `meta.strategyName`| `string` | **Yes** | String | Display name of the strategy. |
| `meta.authorName` | `string` | No | String | Creator's name. |
| `tradingHorizon` | `string` | **Yes** | `"Intraday"`, `"Monthly"`, `"Positional"` | Maps to `INTRADAY` or `DELIVERY`. |
| `timeframe` | `string` | **Yes** | `"5m"`, `"15m"`, `"1h"`, `"Daily"`, `"1d"` | Candle resolution for evaluation. |
| `instrument.type` | `string` | **Yes** | `"Options"`, `"Futures"`, `"Equity"` | Instrument type. |
| `instrument.underlying` | `string` | **Yes** | `"NIFTY 50"`, `"BANKNIFTY"`, `"RELIANCE"`, etc. | Underlying index or stock symbol. |
| `instrument.expiryType` | `string` | **Yes** | `"Weekly"`, `"Monthly"` | Options expiration cycle. |
| `schedule.entryFrom` | `string` | No | `"09:30"`, `""` | Entry window start (HH:MM). Defaults to `"09:15"`. |
| `schedule.entryTo` | `string` | No | `"14:30"`, `""` | Entry window end (HH:MM). Defaults to `"15:00"`. |
| `schedule.forcedExitTime` | `string` | No | `"15:15"`, `""` | Mandatory intraday square-off time. Defaults to `"15:15"`. |
| `entryConditions` | `array[string]` | **Yes** | Non-empty array of rule strings | Entry rules (e.g. `"8 EMA crosses above 33 EMA"`). |
| `exitConditions` | `array[string]` | **Yes** | Non-empty array of rule strings | Exit rules (e.g. `"Target 2R reached"`, `"Forced exit at 15:15"`). |
| `riskManagement.maxLossPerTrade` | `number\|string` | No | `2500`, `"₹2500"`, `""` | Maximum loss per trade in rupees. |
| `riskManagement.maxLossPerDay` | `number\|string` | No | `5000`, `"₹5000"` | Max cumulative daily loss limit. |
| `riskManagement.riskRewardRatio` | `string` | No | `"1:2"`, `"1:3"` | Expected R:R ratio. |
| `target.value` | `string\|number` | **Yes** | `"2R"`, `"Alert Candle Range"`, `"2.5%"` | Target profit formula or percentage. |
| `options.strikeSelection` | `string` | No | `"ATM"`, `"OTM"`, `"ITM"` | Default strike selection policy. |
| `options.legs` | `array[object]` | No | Array of 1 to 4 leg objects | Explicit legs for multi-leg option strategies. |
| `execution.orderType` | `string` | No | `"MARKET"`, `"LIMIT"` | Execution order type. |
| `execution.slippage` | `string\|number` | No | `0.10`, `"0.10%"`, `0.5` | Allowed slippage percentage. |
| `mode` | `string` | No | `"PAPER"`, `"MOCK"`, `"LIVE"` | Execution mode (Defaults to `"PAPER"`). |

#### cURL Example
```bash
curl -X POST "https://api.zenalgo.com/api/strategy" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "schemaVersion": "2.0.0",
    "meta": {
      "strategyId": "EMA_8_33_PULLBACK",
      "strategyName": "8/33 EMA Pullback",
      "authorName": "Ankur"
    },
    "description": "Intraday trend-following strategy using 8 EMA and 33 EMA.",
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
      "Price pulls back to EMA 8 / EMA 33 zone",
      "Confirmation candle breakout triggers entry"
    ],
    "exitConditions": [
      "Target achieved (2R)",
      "Stop loss hit (Confirmation candle low/high)",
      "Opposite EMA crossover",
      "Forced exit at 15:15"
    ],
    "riskManagement": {
      "riskRewardRatio": "1:2",
      "maxLossPerTrade": "₹2500",
      "maxLossPerDay": "₹5000",
      "maxTradesPerDay": "3",
      "capitalAllocationPerTrade": "5%",
      "stopLoss": {
        "type": "Candle High/Low",
        "value": "Confirmation Candle"
      }
    },
    "target": {
      "type": "Risk Reward Multiplier",
      "value": "2R"
    },
    "options": {
      "strikeSelection": "ATM",
      "strikeOffset": "0",
      "optionType": "Dynamic (CE for Bullish, PE for Bearish)"
    },
    "execution": {
      "orderType": "MARKET",
      "executionMode": "PAPER",
      "slippage": "0.10%",
      "orderTimeout": "30s"
    }
  }'
```

#### Success Response (HTTP 201 Created)
```json
{
  "success": true,
  "message": "Strategy created successfully",
  "data": {
    "id": 1042,
    "currentVersionId": 2085,
    "name": "8/33 EMA Pullback",
    "description": "Intraday trend-following strategy using 8 EMA and 33 EMA.",
    "status": "DRAFT",
    "mode": "PAPER",
    "tradingType": "INTRADAY",
    "tradingHorizon": "Intraday",
    "timeframe": "5m",
    "underlying": "NIFTY",
    "capital": "100000.00",
    "maxRiskPerTrade": "2500.00",
    "maxDailyLoss": "5000.00",
    "target": {
      "type": "Risk Reward Multiplier",
      "value": "2R"
    },
    "legs": [
      {
        "id": 501,
        "sequence": 1,
        "segment": "OPT",
        "side": "BUY",
        "optionType": "CE",
        "strikeSelection": "ATM",
        "strikeOffset": 0.0,
        "quantity": 1
      }
    ],
    "schedule": {
      "entryFrom": "09:30",
      "entryTo": "14:30",
      "forcedExitTime": "15:15"
    },
    "createdAt": "2026-09-01T13:45:00Z"
  }
}
```

---

### Endpoint 2: Get Strategy Details (Round-Trip)
- **HTTP Method:** `GET`
- **Route:** `/api/strategy/{id}` *(or `/api/v1/strategies/{id}`)*
- **Auth:** `Bearer <JWT_TOKEN>`

#### Why We Use This API
When the user re-opens an existing strategy in the Frontend Builder to view backtests, edit settings, or inspect performance, this API restores the complete, un-truncated original configuration (including all 4 legs, pivot settings, and event exclusions).

#### cURL Example
```bash
curl -X GET "https://api.zenalgo.com/api/strategy/1042" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### Endpoint 3: Activate Strategy
- **HTTP Method:** `POST`
- **Route:** `/api/strategy/{id}/activate` *(or `/api/v1/strategies/{id}/activate`)*
- **Auth:** `Bearer <JWT_TOKEN>`

#### Why We Use This API
Triggered when the user clicks **"Deploy Paper Trading"**. It moves the strategy runtime state from `WAITING` $\rightarrow$ `MONITORING_ENTRY` and binds it to the live market tick router. If the strategy is already active, it safely returns the existing active runtime state (Idempotent).

#### cURL Example
```bash
curl -X POST "https://api.zenalgo.com/api/strategy/1042/activate" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Success Response (HTTP 200 OK)
```json
{
  "success": true,
  "message": "Strategy activated successfully in PAPER mode",
  "data": {
    "id": 1042,
    "status": "ACTIVE",
    "mode": "PAPER",
    "state": "MONITORING_ENTRY",
    "activeSince": "2026-09-01T13:46:00Z"
  }
}
```

---

### Endpoint 4: List User Strategies
- **HTTP Method:** `GET`
- **Route:** `/api/v1/strategies?status=ACTIVE&page=1&limit=20`
- **Auth:** `Bearer <JWT_TOKEN>`

#### Why We Use This API
Powers the Frontend Strategy Dashboard list view, allowing users to filter by `ACTIVE`, `DRAFT`, or `PAUSED`.

---

### Endpoint 5: Validate Strategy (Pre-Flight Dry-Run)
- **HTTP Method:** `POST`
- **Route:** `/api/v1/strategies/validate`
- **Auth:** `Bearer <JWT_TOKEN>`

#### Why We Use This API
Runs pre-flight syntax and risk validation on a draft payload before committing to the database.

---

## 4. Admin Observability & Execution Tracing Guide

The backend provides complete end-to-end auditability across the entire trade lifecycle:

```
[Strategy ID: 1042]
       │
       ▼
[Strategy Version ID: 2085]  <-- Immutability Guarantee
       │
       ▼
[Market Event Key: 1042:NIFTY:5m:2026-09-01T09:35:00]  <-- Idempotency Boundary
       │
       ▼
[Signal Key: SIG-ENTRY-1042-2085-20260901-0935]
       │
       ▼
[Execution Batch ID: 5501]  <-- Groups Copy-Trading Subscriptions
       │
       ▼
[Correlation ID: TRACE-5501-1042-USR-88-a1b2c3d4]  <-- User-Specific Audit Trace
       │
       ▼
[Execution ID: 7742 & Position ID: 9903]  <-- Paper Broker Order Fills
       │
       ▼
[Exit Signal Key: SIG-EXIT-1042-9903-TARGET-2R]  <-- Exit Engine Evaluation
```

### Admin Strategy & Execution Tracking Endpoints

| HTTP Route | Access Role | Description |
| :--- | :--- | :--- |
| `GET /api/v1/admin/strategies` | `SUPER_ADMIN`, `ADMIN` | Search and filter all strategies across all platform users. |
| `GET /api/v1/admin/strategies/{id}` | `SUPER_ADMIN`, `ADMIN` | Deep-inspect strategy version history, raw parameters, and runtime state. |
| `POST /api/v1/admin/strategies` | `SUPER_ADMIN`, `ADMIN` | Provision or template a strategy on behalf of users. |
| `POST /api/v1/admin/strategies/{id}/activate-paper` | `SUPER_ADMIN`, `ADMIN` | Administrative override to activate PAPER trading. |
| `POST /api/v1/admin/strategies/{id}/activate-live` | `SUPER_ADMIN` | Highly-protected live broker activation switch. |
| `GET /api/v1/admin/execution/strategies/{id}/batches` | `SUPER_ADMIN`, `ADMIN` | **Track how many users executed:** Batch execution history for a strategy (total subscribers, eligible users, successful fills, failures). |
| `GET /api/v1/admin/execution/batches/{id}` | `SUPER_ADMIN`, `ADMIN` | **Batch Summary:** View detailed counts and completion status for a specific execution batch. |
| `GET /api/v1/admin/execution/batches/{id}/traces` | `SUPER_ADMIN`, `ADMIN` | **Track all users in batch:** Per-user status (`EXECUTED`, `FAILED`, `REJECTED`), failure codes, and execution IDs. |
| `GET /api/v1/admin/execution/traces/{trace_id}` | `SUPER_ADMIN`, `ADMIN` | **Track a particular user execution:** Deep dive with full step-by-step event timeline (`USER_CHECK`, `RISK_CHECK`, `BROKER_DISPATCH`). |
| `GET /api/v1/admin/execution/users/{user_id}/traces` | `SUPER_ADMIN`, `ADMIN` | **Track user history:** All execution traces for a specific user across all strategies. |
| `GET /api/v1/admin/execution/batches/{id}/failures` | `SUPER_ADMIN`, `ADMIN` | **Aggregated Failure Breakdown:** Grouped failure counts (e.g. `BROKER_SESSION_INVALID: 4`, `INSUFFICIENT_FUNDS: 2`). |

#### cURL Examples for Execution Tracking:

**1. Track How Many Users Executed a Strategy:**
```bash
curl -X GET "https://api.zenalgo.com/api/v1/admin/execution/strategies/1042/batches?trading_date=2026-09-01" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```
*Response Data:*
```json
{
  "success": true,
  "data": [
    {
      "batchId": 5501,
      "signalId": 1201,
      "strategyId": 1042,
      "strategyVersionId": 2085,
      "tradingDate": "2026-09-01",
      "totalUsers": 150,
      "eligibleUsers": 142,
      "rejectedUsers": 8,
      "executionStartedUsers": 142,
      "successfulUsers": 139,
      "failedUsers": 3,
      "notExecutedUsers": 8,
      "status": "COMPLETED_WITH_ERRORS",
      "createdAt": "2026-09-01T09:35:00Z",
      "completedAt": "2026-09-01T09:35:04Z"
    }
  ]
}
```

**2. Track a Particular User's Execution Timeline:**
```bash
curl -X GET "https://api.zenalgo.com/api/v1/admin/execution/traces/8802" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```
*Response Data:*
```json
{
  "success": true,
  "data": {
    "userId": 42,
    "status": "EXECUTED",
    "currentStep": "ORDER_PLACEMENT",
    "failureCode": null,
    "failureReason": null,
    "timeline": [
      { "step": "INIT", "status": "SUCCESS", "message": "Execution initialized", "timestamp": "2026-09-01T09:35:00Z" },
      { "step": "USER_CHECK", "status": "SUCCESS", "message": "User active and verified", "timestamp": "2026-09-01T09:35:00.100Z" },
      { "step": "SUBSCRIPTION_CHECK", "status": "SUCCESS", "message": "Active Pro plan subscribed", "timestamp": "2026-09-01T09:35:00.200Z" },
      { "step": "RISK_CHECK", "status": "SUCCESS", "message": "Daily loss within limits", "timestamp": "2026-09-01T09:35:00.300Z" },
      { "step": "BROKER_ORDER_PLACEMENT", "status": "SUCCESS", "message": "Market order placed at broker", "timestamp": "2026-09-01T09:35:01.500Z" }
    ]
  }
}
```

---

## 5. Reference Strategy Archetypes & Test Matrix

All 3 authoritative frontend payloads have been verified across 281 automated tests:

### Strategy 1: NIFTY 8/33 EMA Pullback (Single-Leg Option Buying)
- **Timeframe:** `5m` | **Underlying:** `NIFTY 50` | **Expiry:** `Weekly`
- **Execution:** Market order, ATM BUY CE (Bullish) or BUY PE (Bearish).
- **Risk & Target:** Max Loss ₹2,500, Target 2R, 50% partial exit at 1R, forced exit 15:15.

### Strategy 2: NIFTY RSI 60 Alert Candle (Breakout Option Buying)
- **Timeframe:** `15m` | **Underlying:** `NIFTY 50` | **Expiry:** `Weekly`
- **Execution:** BUY CE on Alert Candle High breakout, BUY PE on Low breakout.
- **Risk & Target:** Target = Candle Range, SL = Candle Low/High, Trailing Stop enabled.

### Strategy 3: Reliance Camarilla S3/R3 Pivot Reversal (4-Leg Option Selling)
- **Timeframe:** `Daily` | **Underlying:** `RELIANCE` | **Expiry:** `Monthly`
- **Leg Structure:**
  - `Leg 1`: **SELL CE** (ATM Short)
  - `Leg 2`: **BUY CE** (+200pt OTM Hedge)
  - `Leg 3`: **SELL PE** (ATM Short)
  - `Leg 4`: **BUY PE** (-200pt OTM Hedge)
- **Risk & Target:** 2.5% Target, S3/R3 SL, Quarterly Earnings blackout excluded. All 4 legs exit simultaneously.

---

## 6. Standard Error Codes

| Error Code | HTTP Status | Root Cause | Resolution |
| :--- | :---: | :--- | :--- |
| `TIME_REQUIRED` | `400` | Schedule time missing or invalid format. | Provide time in `HH:MM` format (e.g. `"09:30"`). |
| `INVALID_UNDERLYING` | `400` | Underlying symbol is not supported. | Use `NIFTY`, `BANKNIFTY`, `FINNIFTY`, `RELIANCE`, etc. |
| `INVALID_EXECUTION_PACKAGE` | `422` | Short option leg is missing a protective hedge leg. | Include matching BUY hedge leg in `options.legs`. |
| `EXECUTION_DUPLICATE` | `409` | Signal / execution was already processed. | Safely ignored by the backend idempotency filter. |
| `RISK_LIMIT_EXCEEDED` | `422` | Daily max loss or trade count ceiling reached. | Strategy halts trading for the current session. |
