# ZenAlgo Strategy Specification, Non-Coder Operational Guide & 100% Efficiency Execution Manual

**Comprehensive Guide: How to Login, Configure, and Deploy Strategies Visually Without Writing Code, Automated Protection Firewalls Against Invalid/Uncalculable Entries, Deterministic Rule Grammars, Mathematical Exit Formulations, and Failure-Proof Trading Safeguards.**

---

## 1. Executive Overview: Zero-Discrepancy Automated Trading

The ZenAlgo platform is designed to allow **traders and administrators who do not know any programming code** to build, backtest, and deploy institutional-grade automated strategies. By combining a graphical **Visual Form Builder** with an ultra-strict **Deterministic Calculation Engine**, the software translates plain English trading rules into live algorithmic execution on the broker gateway (Dhan HQ v2) with **100% execution efficiency and 0% execution failure**.

> **Core Operating Principle: Single Source of Mathematical Truth**  
> Every trade decision (entry signal, contract strike resolution, target profit calculation, stop-loss trigger, and 15:15 IST square-off) is governed by centralized mathematical modules in `app/calculation_engine/` and `app/strategies/exit_calculator.py`. Manual guesswork, human emotion, and execution slippage are entirely eliminated.

### Dual-Speed Engine Architecture
* **TICK Mode (Sub-50ms Reaction):** Connects directly to the live Dhan WebSocket feed. Every single incoming price tick is evaluated for contract Last Traded Price (LTP), VWAP, Target Profit, and Stop Loss thresholds. Exit orders are fired immediately when levels are touched.
* **CANDLE_CLOSE Mode (Bar Completion):** Evaluates trend indicators (EMA, RSI, Supertrend, MACD) strictly at the close of the chosen timeframe (`1m`, `3m`, `5m`, `15m`). This protects traders from entering during volatile intra-candle fake spikes that collapse before the candle finishes.

---

## 2. Non-Coder Quick-Start: How to Login & Create a Strategy

Traders and non-technical staff can create and deploy strategies entirely through the web interface using this 7-step workflow:

### Step 1: Login & Broker Authorization
1. Navigate to the web portal and login using your authorized administrator or trader credentials.
2. Go to **"Broker Accounts"** in the navigation menu.
3. Ensure your Dhan broker account is connected and shows status `ACTIVE`. *(Note: Under platform risk rules, each account can connect one broker per calendar day. Ensure authorization is complete before 09:15 AM).*

### Step 2: Navigate to Strategy Builder
Click on **"Strategy Builder"** in the left sidebar. The system automatically opens the **Visual FORM Tab** (selected by default). You never need to touch the JSON tab or write code.

### Step 3: Configure Card 1: Strategy Identity & Market Instrument
* **Strategy Name:** Type a descriptive title (e.g., *"Nifty 8/33 EMA Pullback Scalper"*).
* **Underlying Instrument:** Select from dropdown: `NIFTY 50`, `BANKNIFTY`, `FINNIFTY`, `SENSEX`, or individual stocks (e.g. `RELIANCE`).
* **Candle Timeframe:** Select the bar resolution: `1m`, `3m`, `5m` (recommended for intraday options), or `15m`.
* **Trading Mode:** Select `LIVE` (for real Dhan execution) or `PAPER` (for zero-risk live market testing).
* **Status:** Select `ACTIVE_LIVE` to activate real-time market scanner monitoring.

### Step 4: Configure Card 2: Entry Conditions (3 Ways to Add)
* **Option A (Use Reference Presets):** Select any built-in institutional preset (e.g. *8/33 EMA Pullback*) which auto-populates pre-verified rules.
* **Option B (1-Click AI Strategy Generator):** Click the **"Sparkles"** icon, type what you want in plain words (e.g., *"Buy Nifty CE when 9 EMA crosses 21 EMA above VWAP"*), and click **"Auto-fill Builder"**. The AI validates the indicators and inputs the exact mathematical sentences for you.
* **Option C (Copy-Paste from Section 5):** Click **"+ Add Rule"** and copy-paste any formula from our verified sentence bank (e.g., `CLOSE > EMA(8, CLOSE) AND EMA(8, CLOSE) > EMA(33, CLOSE)`).

### Step 5: Configure Card 3: Multi-Leg Option Contracts & Lots
Click **"+ Add Leg"** to define the trade contract:
* **Action:** `BUY` or `SELL`.
* **Option Type:** `CE` (Call Option) or `PE` (Put Option).
* **Strike Selection:** `ATM` (At-The-Money — recommended), `ITM1`, or `OTM1`.
* **Expiry:** Select `Current Weekly` or `Monthly`.
* **Quantity:** Enter an exact multiple of the lot size (NIFTY = `25, 50, 75`; BANKNIFTY = `15, 30, 45`). The UI automatically converts this to exact lot count.

### Step 6: Configure Card 4: Exit Targets & Risk Management
* **Target Profit:** Enter a percentage (e.g., `2.0%`) or fixed points (e.g., `30 points`).
* **Stop Loss:** Enter a percentage (e.g., `1.0%`) or fixed points (e.g., `15 points`).
* **Trailing Stop Loss (Optional):** Check *"Enable Trailing SL"* and set activation (e.g., after +20 pts profit, trail SL by 5 pts).
* **Mandatory 15:15 Cutoff:** Pre-set by the system to auto-close intraday trades at 15:15 IST.

### Step 7: Save & Deploy
Click **"⚡ Quick Deploy (Live Market)"**. The platform immediately compiles the strategy, spawns a live sub-second market watcher, and monitors the asset for the exact entry trigger.

---

## 3. How the Platform Prevents Uncalculable / Bad Entries (7 Protective Firewalls)

What happens if a non-coder user accidentally enters something invalid, ambiguous, or dangerous? The platform operates **7 automated protective firewalls** that trap errors before any money is risked.

### Firewall 1: The Deterministic Syntax & Grammar Validator
* **The Problem:** A user types an uncalculable sentence such as *"Buy when market looks bullish"* or *"Enter if candle is big green"*.
* **How the Engine Traps It:** The backend runs every rule string through `deterministic_parser.py` and `rule_validator.py`. If a sentence cannot be mathematically mapped to a supported indicator, numerical threshold, or price relation, the system:
  * Assigns a validation status of `INVALID` with an error description (e.g., *"Unsupported condition: no measurable indicator or price relation found"*).
  * Blocks strategy activation with a `400 Bad Request`. No uncalculable trade can ever be executed.

### Firewall 2: Ambiguity Detection & Disambiguation Trap
* **The Problem:** A user types *"RSI above 60"* without specifying whether they mean an instant tick breach or a candle close.
* **How the Engine Traps It:** The parser flags ambiguous phrases with `status="INVALID"` and prompts the user: *"Did you mean: RSI crosses above 60 evaluated at candle close?"*. The engine never guesses user intent.

### Firewall 3: The 50% Available Capital Preservation Gate
* **The Problem:** A user has ₹20,000 in their account but configures a strategy requiring ₹40,000 in margin.
* **How the Engine Traps It:** In `app/execution/service.py` (`evaluate_capital_and_margin`), the engine checks available funds before order placement. **Total required margin cannot exceed 50% of available wallet balance.** If a user has ₹1,00,000, maximum trade margin allowed is ₹50,000. Trades exceeding this are blocked with `ConflictError`.

### Firewall 4: Exchange Lot Sizing Auto-Normalization
* **The Problem:** A user enters quantity `33` on a NIFTY options strategy (where lot size is 25).
* **How the Engine Traps It:** On the frontend and backend (`normalize_leg` in `schemas.py`), the system calculates `lots = round(quantity / lot_size)`. If an invalid quantity is submitted via raw API, the broker adapter rejects the order before transmission to the exchange.

### Firewall 5: Stale Market Data & Disconnection Guard
* **The Problem:** Internet hiccups or exchange WebSocket disconnects cause prices to freeze, risking phantom stop-loss exits.
* **How the Engine Traps It:** In `app/strategies/exit_calculator.py` (`validate_market_quote_freshness`), the engine verifies every tick:
  * Tick age must be < 60 seconds (`age_sec > 60.0` rejects the exit).
  * LTP must be strictly positive (rejects $\le 0$, NaN, or infinite).
  * Trading symbol must match the open position contract.

### Firewall 6: Single Daily Broker Connection Rule
* **The Problem:** Switching broker accounts mid-day causes conflicting orders and duplicate execution tracking.
* **How the Engine Traps It:** Platform enforces that a user can connect only ONE active broker gateway per calendar day. Attempting to connect a second broker returns an immediate conflict error.

### Firewall 7: Mandatory 15:15 IST EOD Auto-Square-Off
* **The Problem:** A user forgets to close an intraday position, risking overnight gap-down losses and broker penalty fees.
* **How the Engine Traps It:** The background scheduler (`workers/scheduler.py`) checks the Asia/Kolkata clock every minute. At exactly **15:15 IST**, all open intraday trades are automatically closed with market orders on the broker gateway.

---

## 4. Supported Technical Indicators & Mathematical Formulas

All 12 native indicators are computed in real time using pure Python and NumPy with zero external TA dependencies:

| Indicator | Default Params | Mathematical Formula | Outputs & Signal Interpretation |
| :--- | :--- | :--- | :--- |
| **RSI** | Period = 14 | `RS = AvgGain / AvgLoss`<br>`RSI = 100 - (100 / (1 + RS))` | Value: 0 to 100.<br>• $\le$ 30: Oversold / reversal BUY.<br>• $\ge$ 70: Overbought / reversal SELL. |
| **EMA** | 8, 9, 20, 21, 33, 50, 200 | `k = 2 / (period + 1)`<br>`EMA[t] = Price[t]*k + EMA[t-1]*(1-k)` | Trend alignment & support/resistance.<br>• 8/33 EMA: High-frequency trend filter.<br>• 9/21 EMA: Standard momentum crossover. |
| **VWAP** | Intraday Cumulative | `VWAP = ∑(TypicalPrice * Vol) / ∑Vol`<br>`TypicalPrice = (H + L + C) / 3` | Institutional fair-value benchmark.<br>• Price > VWAP: Bullish institutional buying.<br>• Price < VWAP: Bearish institutional selling. |
| **MACD** | 12, 26, 9 | `MACD = EMA(12) - EMA(26)`<br>`Signal = EMA(9, MACD)` | Momentum directional shift.<br>• Bullish: MACD line crosses above Signal.<br>• Bearish: MACD line crosses below Signal. |
| **Supertrend** | Period=10, Mult=3.0 | `ATR = RMA(TrueRange, 10)`<br>`Bands = (H+L)/2 ± 3.0 * ATR` | Trailing dynamic stop line.<br>• Value: Active support/resistance level.<br>• Signal: BUY (green) or SELL (red). |
| **Bollinger Bands** | Period=20, StdDev=2.0 | `Middle = SMA(20)`<br>`Upper/Lower = Middle ± 2.0 * σ` | Volatility squeeze & breakout.<br>• Breakout: Price crosses above Upper Band. |
| **Stochastic** | %K=14, %D=3 | `%K = (C - L14)/(H14 - L14)*100`<br>`%D = SMA(3, %K)` | Momentum oscillator (0-100).<br>• < 20: Oversold \| > 80: Overbought. |
| **ADX (+DI/-DI)** | Period=14 | Directional Movement Index.<br>`DX = 100 * |+DI - -DI| / (|+DI + -DI|)` | Trend strength filter.<br>• > 25: Trending market (ideal for options).<br>• < 20: Choppy sideways market (avoid). |
| **CCI** | Period=20 | `CCI = (TP - SMA(TP)) / (0.015 * MeanDev)` | Cyclical momentum index.<br>• > +100: Bullish breakout \| < -100: Breakdown. |
| **MFI** | Period=14 | Volume-weighted RSI from Money Flow Ratio. | Volume-confirmed accumulation / distribution. |
| **Volume SMA** | Avg Period=20 | `Ratio = Current_Vol / SMA(Vol, 20)` | Breakout confirmation.<br>• Ratio > 1.5 indicates genuine institutional volume. |
| **India VIX** | Real-Time Tick | NSE Volatility Index streaming tick. | Volatility regime filter.<br>• Avoid option buying when VIX < 11.5. |

---

## 5. Non-Coder Rule Sentence Bank (Copy-Paste Ready)

Traders can copy and paste any of these 100% verified sentences directly into the strategy builder. Every sentence in this bank has a guaranteed **1.0 parser confidence score**.

### 5.1 Moving Average Trend & Pullback Sentences
* `CLOSE > EMA(8, CLOSE) AND EMA(8, CLOSE) > EMA(33, CLOSE) on 5m candle` (Bullish trend stack)
* `CLOSE < EMA(8, CLOSE) AND EMA(8, CLOSE) < EMA(33, CLOSE) on 5m candle` (Bearish trend stack)
* `9 EMA crosses above 21 EMA on 5m candle` (Fast moving average bullish crossover)
* `9 EMA crosses below 21 EMA on 5m candle` (Fast moving average bearish crossover)
* `Price above 20 EMA on 15m candle` (Medium-term trend alignment)
* `Price crosses above 33 EMA on 5m candle` (Pullback completion breakout above 33 EMA)

### 5.2 VWAP & Institutional Fair-Value Sentences
* `Price above VWAP` (Only trade long when price is above institutional VWAP)
* `Spot below VWAP` (Only trade short when spot price is below institutional VWAP)
* `Price crosses above VWAP on 5m candle` (Bullish VWAP reclaim breakout)
* `Price crosses below VWAP on 5m candle` (Bearish VWAP breakdown)

### 5.3 RSI, Supertrend, MACD & Volatility Sentences
* `RSI above 60 on 15m candle` (Strong upward momentum confirmation)
* `RSI crosses above 50 on 15m candle` (Bullish momentum shift from neutral to positive)
* `Price crosses above Supertrend(10, 3.0) on 15m candle` (Supertrend indicator flips to Buy/Green)
* `Price crosses below Supertrend(10, 3.0) on 15m candle` (Supertrend indicator flips to Sell/Red)
* `MACD bullish crossover on 5m candle` (MACD line crosses above Signal line)
* `Price crosses above upper band of Bollinger Bands on 15m candle` (Volatility expansion breakout)
* `VIX between 11.5 and 18.0` (Trade only during stable volatility regimes)

### 5.4 Mandatory Golden Rules (Candle Confirmation)
* `WAIT_FOR_CANDLE_CLOSE` (Suppresses order dispatch until active bar completes. Prevents whipsaws)
* `CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL` (Requires bar close to remain strictly above breakout price)

---

## 6. Mathematical Exit Calculations & Live Monitoring

The Multi-Exit Watcher calculates dynamic price levels on every market tick. Below are the exact mathematical formulas:

```text
BUY (CALL / LONG) POSITION FORMULAS:
Target Price = EntryPrice * (1 + Target% / 100)
StopLoss Price = EntryPrice * (1 - SL% / 100)
Target Profit (₹) = (Target Price - Entry) * Qty
Max Risk (₹) = (StopLoss Price - Entry) * Qty
Live PnL (₹) = (Current LTP - Entry) * Qty

Trigger Checks:
• Target Hit IF: (LTP >= Target Price) OR (PnL >= Target Profit)
• SL Hit IF: (LTP <= SL Price) OR (PnL <= Max Risk)
```

```text
SELL (PUT / SHORT) POSITION FORMULAS:
Target Price = EntryPrice * (1 - Target% / 100)
StopLoss Price = EntryPrice * (1 + SL% / 100)
Target Profit (₹) = (Entry - Target Price) * Qty
Max Risk (₹) = (Entry - StopLoss Price) * Qty
Live PnL (₹) = (Entry - Current LTP) * Qty

Trigger Checks:
• Target Hit IF: (LTP <= Target Price) OR (PnL >= Target Profit)
• SL Hit IF: (LTP >= SL Price) OR (PnL <= Max Risk)
```

### Fixed Points vs. Percentage Modes
* **Percentage Mode (Default):** Target and SL move proportionally to the option premium (e.g. 2% target on ₹100 premium = ₹102.00 target price).
* **Points Mode:** Target and SL are absolute points (e.g. 30 points target on ₹100 premium = ₹130.00 target price).
* **Tick Size Rounding:** All calculated prices are automatically rounded to the nearest exchange tick (0.05 paise) via `round_to_tick(price, 0.05)`.

### Dynamic Trailing Stop Loss Workflow
1. **Profit Activation:** Trailing activates only after the trade reaches a minimum profit threshold (e.g., +20 points).
2. **Step Increment:** For each additional profit step (e.g., +10 points)...
3. **Trail Execution:** The Stop Loss price is automatically moved up by the specified trail amount, locking in accrued gains.

---

## 7. Operator Troubleshooting & Error Resolutions

| Error Code / Message | Root Cause | How to Fix in 5 Seconds |
| :--- | :--- | :--- |
| `AMBIGUOUS_RULE` | Rule sentence lacks timeframe or clear operator (e.g. "RSI above 60"). | Change sentence to: `RSI above 60 on 15m candle` or choose a pre-tested sentence from Section 5. |
| `UNSUPPORTED_INDICATOR` | Typo in indicator name (e.g. "EMMA" instead of "EMA"). | Check spelling against the 12 supported indicators in Section 4. |
| `INSUFFICIENT_MARGIN` (50% Gate) | Required trade margin exceeds 50% of available account wallet balance. | Reduce trade quantity/lots or deposit funds into wallet to meet the 2x margin requirement. |
| `INVALID_LOT_QUANTITY` | Submitted quantity is not a valid lot multiple (e.g. 33 on NIFTY). | Change quantity to an exact lot multiple (NIFTY = 25, 50, 75; BANKNIFTY = 15, 30, 45). |
| `CONFLICT_DAILY_BROKER` | Account tried connecting a second broker on the same calendar day. | Platform allows 1 broker connection per calendar day. Use the existing connected broker or reconnect tomorrow. |
| `STALE_MARKET_DATA` | Market data feed age exceeds 60 seconds (WebSocket disconnection). | Automatic protection is active. Check internet connection and verify Dhan broker session token is active. |
| `BROKER_TOKEN_EXPIRED` | Dhan daily OAuth token has expired (daily 24-hour validity). | Go to Broker Accounts, click Re-Authorize Dhan, and generate a fresh daily token. |

---

## 8. Ready-to-Deploy Reference Strategy Templates

### Template 1: 8/33 EMA Pullback Intraday Strategy (NIFTY Options)
```json
{
  "name": "NIFTY 8/33 EMA Pullback Master",
  "underlying": "NIFTY 50",
  "category": "Option Buying - Index",
  "strategyStyle": "Trend Following",
  "tradingHorizon": "Intraday",
  "mode": "LIVE",
  "status": "ACTIVE_LIVE",
  "entryConditions": [
    "CLOSE > EMA(8, CLOSE) AND EMA(8, CLOSE) > EMA(33, CLOSE) on 5m candle",
    "Price pulls back toward EMA(33, CLOSE)"
  ],
  "exitConditions": [
    "CLOSE < EMA(8, CLOSE) OR RSI(14, CLOSE) < 40 on 5m candle",
    "Target of 2R is achieved",
    "15:15 intraday square off"
  ],
  "config": {
    "timing": { "entryFrom": "09:20", "forcedExitTime": "15:15" },
    "target": { "value": "2.0", "type": "PERCENTAGE" },
    "riskManagement": { "stopLoss": { "value": "1.0", "type": "PERCENTAGE" }, "maxLossPerTrade": "2500" },
    "options": {
      "legs": [
        { "action": "BUY", "type": "CE", "strike": "ATM", "expiry": "Current Weekly", "quantity": 50, "lots": 2 }
      ]
    }
  }
}
```

### Template 2: Supertrend Momentum + Trailing Stop Loss (Cash/F&O)
```json
{
  "name": "Supertrend Breakout Pro",
  "underlying": "RELIANCE",
  "category": "Equity Cash",
  "mode": "LIVE",
  "status": "ACTIVE_LIVE",
  "entryConditions": [
    "Price crosses above Supertrend(10, 3.0) on 15m candle",
    "RSI(14, CLOSE) > 55"
  ],
  "exitConditions": [
    "Price crosses below Supertrend(10, 3.0) on 15m candle",
    "15:15 intraday square off"
  ],
  "config": {
    "target": { "value": "3.0", "type": "PERCENTAGE" },
    "riskManagement": { "stopLoss": { "value": "1.5", "type": "PERCENTAGE" } },
    "legs": [
      {
        "action": "BUY",
        "quantity": 100,
        "lots": 100,
        "trailing_sl_enabled": true,
        "trailing_sl_activate_value": 15.0,
        "trailing_sl_increase_by": 5.0,
        "trailing_sl_by": 5.0
      }
    ]
  }
}
```

---

### 100% Efficiency Pre-Flight Checklist:
* [x] Broker account (Dhan) verified connected with active token for today.
* [x] Strategy entry rule selected from Section 5 sentence bank.
* [x] Quantity matches exact exchange lot size (Equities: 1, NIFTY: 25, BANKNIFTY: 15).
* [x] Required margin is $\le 50\%$ of available account balance.
* [x] Target Profit (% or pts) and Stop Loss (% or pts) entered.
* [x] Mode is set to `LIVE` and status is `ACTIVE_LIVE`.
