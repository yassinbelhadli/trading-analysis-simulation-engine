from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from news_engine.parsers.json_parser import JSONParser


class FundamentalState:

    def __init__(self, path: str = "data/processed/fundamental_state.json"):
        self.path = Path(path)
        self.parser = JSONParser()

        if not self.path.exists():
            self.parser.write(self.path, {})

    def load(self) -> Dict:
        return self.parser.read(self.path)

    def save(self, state: Dict):
        self.parser.write(self.path, state)

    def update_currency(
        self,
        currency: str,
        bias: str,
        strength: float,
        confidence: float,
        reason: str,
        last_event: str = "",
        impact: str = "",
        source: str = "ForexFactory",
    ):
        state = self.load()

        state[currency.upper()] = {
            "bias": bias,
            "strength": strength,
            "confidence": confidence,
            "reason": reason,
            "last_event": last_event,
            "impact": impact,
            "source": source,
            "updated_at": datetime.utcnow().isoformat(),
        }

        self.save(state)

    def get_currency(self, currency: str) -> Optional[Dict]:
        state = self.load()
        return state.get(currency.upper())