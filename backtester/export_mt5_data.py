import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path

SYMBOL = "XAUUSD"      # بدلها حسب البروكر: GOLD / XAUUSD / XAUUSDm
TIMEFRAME = mt5.TIMEFRAME_M15
BARS = 5000

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / f"{SYMBOL}_M15.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

if not mt5.initialize():
    raise RuntimeError("MT5 initialize failed")

rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, BARS)

if rates is None:
    mt5.shutdown()
    raise RuntimeError(f"No data returned for {SYMBOL}")

df = pd.DataFrame(rates)
df["Time"] = pd.to_datetime(df["time"], unit="s")
df.rename(columns={
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "tick_volume": "Volume"
}, inplace=True)

df = df[["Time", "Open", "High", "Low", "Close", "Volume"]]
df.to_csv(OUT, index=False)

mt5.shutdown()
print(f"Saved: {OUT}")