import re

# Timeframe detection suffix: optionally matches "on 15m candle/chart/timeframe"
TF_SUFFIX = r"(?:\s+on\s+([135mhd0-9]+)(?:\s+candle|\s+chart|\s+timeframe)?)?"

# evaluation type: candle close
CANDLE_CLOSE_PAT = r"(?:\s+evaluated\s+at\s+candle\s+close)?"

# 1. Indicator-to-Indicator crossover (e.g., "9 EMA crosses above 21 EMA")
IND_IND_CROSS = re.compile(
    r"^(?:(\d+)\s+)?(EMA|SMA|VWAP|RSI)(?:\((\d+)\))?\s+"
    r"(crosses\s+above|crosses\s+below|crosses|crossover\s+above|crossover\s+below)\s+"
    r"(?:(\d+)\s+)?(EMA|SMA|VWAP|RSI)(?:\((\d+)\))?" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 2. Indicator to Constant comparison (e.g., "RSI above 60", "VIX < 11.5")
IND_CONST_COMP = re.compile(
    r"^(EMA|SMA|VWAP|RSI|VIX)(?:\((\d+)\))?\s+"
    r"(above|below|is\s+above|is\s+below|greater\s+than|less\s+than|<=|>=|<|>)\s+"
    r"(\d+(?:\.\d+)?)" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 3. Indicator to Constant crossover (e.g., "RSI crosses above 60")
IND_CONST_CROSS = re.compile(
    r"^(EMA|SMA|VWAP|RSI|VIX)(?:\((\d+)\))?\s+"
    r"(crosses\s+above|crosses\s+below|crossover\s+above|crossover\s+below)\s+"
    r"(\d+(?:\.\d+)?)" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 4. Price to Indicator comparison (e.g., "Price above 20 EMA", "Spot below VWAP")
PRICE_IND_COMP = re.compile(
    r"^(Price|Spot)\s+(above|below|is\s+above|is\s+below|greater\s+than|less\s+than)\s+"
    r"(?:(\d+)\s+)?(EMA|SMA|VWAP)(?:\((\d+)\))?" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 5. Price to Indicator crossover (e.g., "Price crosses above 20 EMA")
PRICE_IND_CROSS = re.compile(
    r"^(Price|Spot)\s+(crosses\s+above|crosses\s+below|crossover\s+above|crossover\s+below)\s+"
    r"(?:(\d+)\s+)?(EMA|SMA|VWAP)(?:\((\d+)\))?" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 6. Price to Constant comparison (e.g., "Price above 24000")
PRICE_CONST_COMP = re.compile(
    r"^(Price|Spot)\s+(above|below|is\s+above|is\s+below|greater\s+than|less\s+than)\s+"
    r"(\d+(?:\.\d+)?)" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 7. Price to Constant crossover (e.g., "Price crosses above 24000")
PRICE_CONST_CROSS = re.compile(
    r"^(Price|Spot)\s+(crosses\s+above|crosses\s+below|crossover\s+above|crossover\s+below)\s+"
    r"(\d+(?:\.\d+)?)" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 8. Bollinger Bands crossover / comparison (e.g., "Price above upper band")
BB_RULE = re.compile(
    r"^(Price|Spot)\s+"
    r"(above|below|is\s+above|is\s+below|crosses\s+above|crosses\s+below|crossover\s+above|crossover\s+below)\s+"
    r"(upper\s+band|lower\s+band)\s*"
    r"(?:of\s+Bollinger\s+Bands|of\s+BB)?(?:\((\d+)\))?" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 9. MACD Crossover (e.g., "MACD bullish crossover")
MACD_CROSS = re.compile(
    r"^(MACD)\s+(?:crossover\s+)?(bullish|bearish)" + TF_SUFFIX + CANDLE_CLOSE_PAT + r"$",
    re.IGNORECASE
)

# 10. Confirmation rule prefix (e.g., "Wait for candle closure")
CONFIRMATION_PREFIX = re.compile(
    r"^(wait\s+for|check|confirm)\s+(.+)$",
    re.IGNORECASE
)

# 11. Time Exit (e.g., "Exit at 15:15")
TIME_EXIT_PAT = re.compile(
    r"^exit\s+at\s+(\d{2}:\d{2})$",
    re.IGNORECASE
)
