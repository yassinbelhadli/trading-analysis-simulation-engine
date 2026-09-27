import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

from core_engine.execution.entry_manager import EntryManager
from core_engine.risk.account_profile import AccountProfileBuilder


manager = EntryManager()

manager.fundamental_state.update_currency(
    currency="USD",
    bias="BEARISH",
    strength=100,
    confidence=100,
    reason="Test USD bearish",
    last_event="Core PCE",
    impact="HIGH",
    source="TEST",
)

builder = AccountProfileBuilder()

profile = builder.create_profile(
    client_id="TEST_CLIENT",
    account_type="PERSONAL",
    balance=10000,
    equity=10000,
    symbol="XAUUSD",
    primary_symbol="XAUUSD",
    allowed_symbols=["XAUUSD"],
    enabled_markets=["GOLD"],
)

row = pd.Series({
    "Trade_Direction": "BUY",
    "Setup_Approved": True,
    "Confidence_Approved": True,
    "Confidence_Score": 90,
    "Setup_Score": 90,

    "Session_Trade_Allowed": True,
    "London_Trade_Allowed": True,
    "NewYork_Trade_Allowed": False,

    "Active_OB_Type": "Bullish",
    "Active_FVG_Type": "Bullish",

    "Active_OB_Midpoint": 3350,
    "Active_OB_Lower": 3348,
    "Active_OB_Upper": 3352,

    "Active_FVG_Midpoint": 3350,
    "Active_FVG_Lower": 3348,
    "Active_FVG_Upper": 3352,

    "ATR": 10,
    "Close": 3351,
    "Low": 3345,
    "High": 3355,
})

row.name = pd.Timestamp("2026-06-27 10:00:00")

decision = manager.build_entry_decision(
    row=row,
    profile=profile,
    current_equity=10000,
    daily_start_equity=10000,
    trading_mode="BALANCED",
)

print("=" * 70)
print("BUY TEST")
print("Reason:", decision.reason)
print("Can execute:", decision.can_execute)
print("=" * 70)

row_sell = row.copy()
row_sell["Trade_Direction"] = "SELL"
row_sell["Active_OB_Type"] = "Bearish"
row_sell["Active_FVG_Type"] = "Bearish"

decision_sell = manager.build_entry_decision(
    row=row_sell,
    profile=profile,
    current_equity=10000,
    daily_start_equity=10000,
    trading_mode="BALANCED",
)

print("=" * 70)
print("SELL TEST")
print("Reason:", decision_sell.reason)
print("Can execute:", decision_sell.can_execute)
print("=" * 70)