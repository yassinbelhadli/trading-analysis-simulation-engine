"""Score Engine — evaluates the strength of a market setup across all detection modules.

Maps raw detection data to a unified confidence score (0-100) with classification
and directional bias.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Weight presets for ablation experiments ─────────────────────
EXPERIMENTS = {
    "v1_default": {
        "bos": 20, "bos_hidden": 5, "choch": 15, "mss": 20,
        "sweep": 15, "active_ob_fvg": 20, "pd_alignment": 10,
    },
    # Experiment 1: Reduce MSS, reduce Sweep, boost BOS
    "v2_structure_focus": {
        "bos": 25, "bos_hidden": 5, "choch": 15, "mss": 10,
        "sweep": 10, "active_ob_fvg": 20, "pd_alignment": 10,
    },
    # Experiment 3: Sweep weight halved
    "v3_reduce_sweep": {
        "bos": 20, "bos_hidden": 5, "choch": 15, "mss": 20,
        "sweep": 8, "active_ob_fvg": 20, "pd_alignment": 10,
    },
    # Experiment 4: Equalize BOS/CHoCH/MSS weights
    "v4_equal_structure": {
        "bos": 17, "bos_hidden": 5, "choch": 17, "mss": 17,
        "sweep": 15, "active_ob_fvg": 20, "pd_alignment": 10,
    },
}

# Default weights (used when no experiment name given)
DEFAULT_WEIGHTS = EXPERIMENTS["v1_default"]


def set_experiment(name: str = None) -> Dict:
    """Switch to a named weight preset. Returns the active weights."""
    global WEIGHTS, MAX_POSSIBLE
    if name is None or name not in EXPERIMENTS:
        WEIGHTS = dict(DEFAULT_WEIGHTS)
    else:
        WEIGHTS = dict(EXPERIMENTS[name])
    MAX_POSSIBLE = sum(WEIGHTS.values())
    return WEIGHTS


set_experiment("v1_default")

CLASSIFICATIONS = [
    (0, 39, "ignore"),
    (40, 59, "watch"),
    (60, 79, "setup"),
    (80, 100, "high_confidence"),
]


def _classify(score: int) -> str:
    for lo, hi, label in CLASSIFICATIONS:
        if lo <= score <= hi:
            return label
    return "ignore"


def _determine_direction(result: Dict) -> str:
    """Vote on directional bias from all signals."""
    votes = {"bullish": 0, "bearish": 0}

    # BOS direction
    for b in result.get("bos", []):
        d = b.get("direction")
        if d == "bullish":
            votes["bullish"] += 2
        elif d == "bearish":
            votes["bearish"] += 2

    # Hidden BOS direction
    for b in result.get("bos_hidden", []):
        d = b.get("direction")
        if d == "bullish":
            votes["bullish"] += 1
        elif d == "bearish":
            votes["bearish"] += 1

    # CHoCH direction
    for c in result.get("choch", []):
        d = c.get("direction")
        if d == "bullish":
            votes["bullish"] += 3
        elif d == "bearish":
            votes["bearish"] += 3

    # MSS direction
    for m in result.get("mss", []):
        d = m.get("direction")
        if d == "bullish":
            votes["bullish"] += 4
        elif d == "bearish":
            votes["bearish"] += 4

    # Sweep direction (BSL = bullish, SSL = bearish)
    sweep_type = result.get("sweep_type")
    if sweep_type == "BSL":
        votes["bullish"] += 3
    elif sweep_type == "SSL":
        votes["bearish"] += 3

    # Active zone direction
    for z in result.get("zones", []):
        d = z.get("direction")
        if z.get("active") or z.get("fresh"):
            if d == "bullish":
                votes["bullish"] += 1
            elif d == "bearish":
                votes["bearish"] += 1

    # PD alignment vote (price in premium is bearish bias, in discount is bullish bias)
    equity = result.get("equilibrium")
    if equity is not None:
        latest_price = None
        # Could get from candles if available, but use PDH/PDL as proxy
        pdh = result.get("pdh")
        pdl = result.get("pdl")
        if pdh and pdl:
            mid = (pdh + pdl) / 2
            # If above equilibrium → bearish bias
            # If below equilibrium → bullish bias
            # (using PDH/PDL as rough proxy)
            pdh_dist = abs(pdh - equity) if pdh else 1
            pdl_dist = abs(pdl - equity) if pdl else 1
            if pdl_dist > 0 and pdh_dist > 0:
                pass  # inconclusive without current price

    total_votes = votes["bullish"] + votes["bearish"]
    if total_votes == 0:
        return "neutral"
    if votes["bullish"] > votes["bearish"]:
        return "bullish"
    elif votes["bearish"] > votes["bullish"]:
        return "bearish"
    return "neutral"


def _score_bos(result: Dict) -> int:
    """BOS component: 0-20 based on score of latest BOS."""
    bos_list = result.get("bos", [])
    if not bos_list:
        return 0
    latest = bos_list[0]
    s = latest.get("score", 0)
    # Scale 0-100 → 0-20
    return min(20, max(0, int(s * 0.2)))


def _score_hidden_bos(result: Dict) -> int:
    """Hidden BOS bonus: +5 if hidden BOS in same direction as main bias."""
    hidden = result.get("bos_hidden", [])
    if not hidden:
        return 0
    direction = result.get("_direction", "neutral")
    if direction == "neutral":
        return 0
    for h in hidden:
        if h.get("direction") == direction:
            return 5
    return 0


def _score_choch(result: Dict) -> int:
    """CHoCH component: 0-15."""
    choch_list = result.get("choch", [])
    if not choch_list:
        return 0
    # Full points if aligned with direction
    direction = result.get("_direction", "neutral")
    if direction == "neutral":
        return 10
    for c in choch_list:
        if c.get("direction") == direction:
            return 15
    return 10


def _score_mss(result: Dict) -> int:
    """MSS component: 0-20."""
    mss_list = result.get("mss", [])
    if not mss_list:
        return 0
    latest = mss_list[0]
    direction = result.get("_direction", "neutral")
    confirm = latest.get("confirm_score", 0)
    # Bonus for high confirmation score
    aligned = 1 if direction != "neutral" and latest.get("direction") == direction else 0
    if aligned and confirm >= 70:
        return 20
    if aligned:
        return 15
    return 10


def _score_sweep(result: Dict) -> int:
    """Liquidity sweep component: 0-15."""
    if not result.get("sweep_type"):
        return 0
    direction = result.get("_direction", "neutral")
    # Determine if sweep aligns with direction
    sweep_aligned = False
    sweep_type = result.get("sweep_type")
    if direction == "bullish" and sweep_type == "BSL":
        sweep_aligned = True
    elif direction == "bearish" and sweep_type == "SSL":
        sweep_aligned = True

    linked_bos_score = result.get("linked_bos_score")
    if sweep_aligned and linked_bos_score and linked_bos_score >= 60:
        return 15
    if sweep_aligned:
        return 12
    if linked_bos_score and linked_bos_score >= 60:
        return 10
    return 8


def _score_active_zones(result: Dict) -> int:
    """Active zone component: 0-10 for OB, 0-10 for FVG."""
    zones = result.get("zones", [])
    direction = result.get("_direction", "neutral")
    if not zones:
        return 0

    ob_score = 0
    fvg_score = 0

    for z in zones:
        is_aligned = direction == "neutral" or z.get("direction") == direction
        if not is_aligned:
            continue
        if z["type"] == "OB" and (z.get("active") or z.get("fresh")):
            ob_score = 10  # max 10
        if z["type"] == "FVG" and (z.get("active") or z.get("fresh")):
            fvg_score = 10  # max 10

    return ob_score + fvg_score  # max 20


def _score_pd_alignment(result: Dict) -> int:
    """Premium/Discount alignment: 0-10."""
    direction = result.get("_direction", "neutral")
    if direction == "neutral":
        return 0
    equity = result.get("equilibrium")
    if equity is None:
        return 0

    pdh = result.get("pdh")
    pdl = result.get("pdl")
    if pdh is None or pdl is None or pdh == pdl:
        return 0

    # Check if price is in premium (above equilibrium) or discount (below)
    # We approximate with pdh/pdl as the boundaries
    premium_zone = (equity + pdh) / 2
    discount_zone = (equity + pdl) / 2

    # Current price isn't directly available in result, estimate from recent zones
    # Use PDH/PDL as price reference
    current_price = pdh  # approximate

    if direction == "bullish":
        # Bullish setup stronger when price is in discount zone
        if current_price <= equity:
            return 10
        return 5
    else:
        # Bearish setup stronger when price is in premium zone
        if current_price >= equity:
            return 10
        return 5


def score_setup(result: Dict) -> Dict:
    """Score the current market setup from engine analysis output.

    Args:
        result: dict from engine.analyze()

    Returns:
        {
            "score": int (0-100),
            "classification": "ignore" | "watch" | "setup" | "high_confidence",
            "direction": "bullish" | "bearish" | "neutral",
            "breakdown": {component: score, ...},
            "signal": str (short description),
            "setup_found": bool,
        }
    """
    if not result:
        return {
            "score": 0,
            "classification": "ignore",
            "direction": "neutral",
            "breakdown": {},
            "signal": "No data",
            "setup_found": False,
        }

    # Determine direction (stored for sub-scorers)
    direction = _determine_direction(result)
    result["_direction"] = direction

    # Score each component
    breakdown = {
        "bos": _score_bos(result),
        "bos_hidden": _score_hidden_bos(result),
        "choch": _score_choch(result),
        "mss": _score_mss(result),
        "sweep": _score_sweep(result),
        "active_ob_fvg": _score_active_zones(result),
        "pd_alignment": _score_pd_alignment(result),
    }

    total = sum(breakdown.values())
    # Normalize to 0-100
    score = min(100, int((total / MAX_POSSIBLE) * 100))

    classification = _classify(score)

    # Build short signal description
    parts = []
    if direction != "neutral":
        parts.append(direction.upper())
    if result.get("sweep_type"):
        if direction == "bullish" and result["sweep_type"] == "BSL":
            parts.append("BSL Swept")
        elif direction == "bearish" and result["sweep_type"] == "SSL":
            parts.append("SSL Swept")
        else:
            parts.append("Sweep")
    for b in result.get("bos", []):
        if b.get("direction") == direction:
            score_label = b.get("classification", "")
            if score_label:
                parts.append(f"{score_label} BOS")
    if result.get("mss") and direction != "neutral":
        parts.append("MSS")
    if result.get("choch") and direction != "neutral":
        parts.append("CHoCH")
    active_obs = sum(1 for z in result.get("zones", [])
                     if z["type"] == "OB" and (z.get("active") or z.get("fresh")))
    active_fvgs = sum(1 for z in result.get("zones", [])
                      if z["type"] == "FVG" and (z.get("active") or z.get("fresh")))
    if active_obs:
        parts.append("OBx%d" % active_obs)
    if active_fvgs:
        parts.append("FVGx%d" % active_fvgs)

    signal = " | ".join(parts) if parts else "No clear setup"
    # Remove _direction internal key
    result.pop("_direction", None)

    return {
        "score": score,
        "classification": classification,
        "direction": direction,
        "breakdown": breakdown,
        "signal": signal,
        "setup_found": score >= 60,
    }
