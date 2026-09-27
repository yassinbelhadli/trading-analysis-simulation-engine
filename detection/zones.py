"""Premium / Discount zone calculation from visible range."""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def calc_premium_discount(candles: List[Dict]) -> dict:
    """Calculate the equilibrium and premium/discount zones.

    Premium: above the 50% midpoint of the visible range.
    Discount: below the 50% midpoint.

    Returns {equilibrium, premium_high, discount_low}
    """
    if not candles:
        return {}
    vis_high = max(c["high"] for c in candles)
    vis_low = min(c["low"] for c in candles)
    equilibrium = (vis_high + vis_low) / 2
    # Premium zone: above equilibrium (50-100%)
    # Discount zone: below equilibrium (0-50%)
    return {
        "equilibrium": equilibrium,
        "premium_high": vis_high,
        "discount_low": vis_low,
    }
