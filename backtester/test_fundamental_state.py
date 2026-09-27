import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_engine.fundamental_state import FundamentalState

state = FundamentalState()

state.update_currency(

    currency="USD",

    bias="BULLISH",

    strength=95,

    confidence=91,

    reason="Core PCE Positive"

)

print(state.get_currency("USD"))