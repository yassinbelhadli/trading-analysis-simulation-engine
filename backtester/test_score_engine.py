import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd

from core_engine.scoring.score_engine import ScoreEngine


df = pd.DataFrame([
    {
        "MSS": True,
        "MSS_Type": "Bullish",
        "CHoCH": True,
        "CHoCH_Type": "Bullish",
        "BOS": True,
        "BOS_Type": "Bullish",
        "Valid_Sweep": True,
        "Sweep_Strength": 8,
        "Bullish_FVG": True,
        "Bullish_OB": True,
        "Bullish_VI": True,
        "Bullish_LV": True,
        "PD_State": "DISCOUNT",
        "Near_Support": True,
        "Candle_Direction": "Bullish",
    }
])

engine = ScoreEngine()
result = engine.process_score(df)

print(result[[
    "Setup_Score",
    "Trade_Direction",
    "Direction_Source",
    "Setup_Quality",
]].to_string(index=False))