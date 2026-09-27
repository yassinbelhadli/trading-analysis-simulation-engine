import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from core_engine.execution.entry_manager import EntryManager
from core_engine.risk.account_profile import AccountProfileBuilder

builder = AccountProfileBuilder()

profile = builder.create_profile(
    client_id="test",
    account_type="PERSONAL",
    balance=10000,
)

manager = EntryManager()

base = {
    "Trade_Direction": "BUY",
    "Setup_Approved": True,
    "Confidence_Approved": True,
    "Confidence_Score": 90,

    "Session_Trade_Allowed": True,

    "Active_OB_Type": "Bullish",
    "Active_OB_Valid": True,

    "Active_OB_Lower": 3290,
    "Active_OB_Upper": 3300,
    "Active_OB_Midpoint": 3295,

    "Close": 3296,
    "ATR": 5,
    "Low": 3289,
    "High": 3298,

    "Setup_ID": "TEST001",
    "Session_Name": "LONDON",
}

for score in [55, 70, 85, 95]:

    row = pd.Series(base)
    row["Setup_Score"] = score

    result = manager.build_entry_decision(
        row=row,
        profile=profile,
        current_equity=10000,
        daily_start_equity=10000,
        trading_mode="BALANCED",
    )

    print("=" * 60)
    print("Setup Score :", score)
    print("Can Execute :", result.can_execute)
    print("Lot Size    :", result.lot_size)
    print("Risk %      :", result.metadata["dynamic_risk_percent"])