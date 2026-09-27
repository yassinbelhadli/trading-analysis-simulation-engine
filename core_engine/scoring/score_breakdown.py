from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class ScoreBreakdown:

    total_score: float = 0.0
    quality: str = "IGNORE"

    direction: str = ""
    direction_source: str = ""

    structure: float = 0.0
    liquidity: float = 0.0
    order_block: float = 0.0
    fair_value_gap: float = 0.0
    volume_imbalance: float = 0.0
    liquidity_void: float = 0.0
    premium_discount: float = 0.0
    support_resistance: float = 0.0
    candle_confirmation: float = 0.0
    context: float = 0.0

    reasons: Dict = None

    def to_dict(self):
        data = asdict(self)

        if data["reasons"] is None:
            data["reasons"] = {}

        return data