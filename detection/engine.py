"""ICT Detection Engine: orchestrates all detection, produces unified signal dict.

Structure detection uses a sequential State Machine:
  - Stateful trend tracking (BULLISH/BEARISH/RANGING)
  - BOS emitted once per swing level
  - CHoCH only on trend reversals with cooldown
  - MSS requires confirmation swing after CHoCH
"""

import logging
from typing import List, Dict, Optional

from detection.swing import detect_swings, classify_swings, latest_swing_highs, latest_swing_lows
from detection.structure_state_machine import detect_structure
from detection.order_block import detect_obs
from detection.fvg import detect_fvgs, link_fvgs_to_structure
from detection.mitigation import build_zones, scan_zones, filter_active_zones
from detection.scoring import score_setup, set_experiment
from detection.liquidity import detect_sweep, detect_equal_highs_lows, get_pdh_pdl
from detection.zones import calc_premium_discount
from detection.bos_scorer import classify_bos
from detection.conflict_resolver import resolve

logger = logging.getLogger(__name__)


def analyze(candles: List[Dict], experiment: str = None) -> dict:
    """Run full ICT detection pipeline using sequential state machine.

    Args:
        candles: OHLC data
        experiment: scoring preset name (None = v1_default)

    Returns unified signal dict for the drawing engine.
    """
    if experiment:
        set_experiment(experiment)
    if not candles or len(candles) < 20:
        logger.warning("Not enough candles for detection")
        return {}

    # 1. Swing detection (full classification for OB/FVG/liquidity)
    raw = detect_swings(candles)
    swings = classify_swings(raw)

    # 2. Structure via State Machine (sole source of BOS/CHoCH/MSS)
    sm = detect_structure(candles, raw)
    bos = sm["bos"]
    choch = sm["choch"]
    mss = sm["mss"]

    # 3. Score BOS events
    bos = classify_bos(bos, swings, candles)

    # 4. Conflict resolution (continuation marking + safety dedup)
    resolved = resolve(swings, bos, choch, mss)

    # 5. Order Blocks (anchored to BOS/CHoCH/MSS)
    obs = detect_obs(candles, swings,
                     bos_list=resolved["bos"],
                     choch_list=resolved["choch"],
                     mss_list=resolved["mss"])

    # 6. FVGs (linked to structure events only)
    all_fvgs = detect_fvgs(candles)
    all_fvgs = link_fvgs_to_structure(all_fvgs,
                                      bos_list=resolved["bos"],
                                      choch_list=resolved["choch"],
                                      mss_list=resolved["mss"],
                                      max_distance=3)
    fvgs = [f for f in all_fvgs if f["origin_event"] is not None]

    # 7. Unified Mitigation Engine (both OB + FVG as zones)
    zones = build_zones(obs, fvgs)
    zones = scan_zones(zones, candles)
    active_zones = filter_active_zones(zones, max_count=5)

    # 8. Liquidity (with BOS linking)
    sweep = detect_sweep(candles, swings, resolved["bos"]) or {}
    eq_hl = detect_equal_highs_lows(swings)
    dh_pdl = get_pdh_pdl(candles, swings)

    # 9. Premium / Discount
    pd_zones = calc_premium_discount(candles)

    # 9. Last swings for labels
    last_hhs = latest_swing_highs(swings, count=2)
    last_lls = latest_swing_lows(swings, count=2)

    result = {
        "swings": last_hhs + last_lls,
        "state": sm["state_history"]["final_state"],
        "bos": resolved["bos"][-1:] if resolved["bos"] else [],
        "bos_hidden": resolved["bos_hidden"][-1:] if resolved["bos_hidden"] else [],
        "choch": resolved["choch"][-1:] if resolved["choch"] else [],
        "mss": resolved["mss"][-1:] if resolved["mss"] else [],
        "order_blocks": obs,
        "fvgs": fvgs[-3:] if fvgs else [],
        "zones": active_zones,
        "equal_highs": eq_hl.get("equal_highs", []),
        "equal_lows": eq_hl.get("equal_lows", []),
        "pdh": dh_pdl.get("pdh"),
        "pdl": dh_pdl.get("pdl"),
        "equilibrium": pd_zones.get("equilibrium"),
        "premium_high": pd_zones.get("premium_high"),
        "discount_low": pd_zones.get("discount_low"),
    }

    # Add sweep keys only if detected
    if sweep.get("sweep_type"):
        result["sweep_price"] = sweep["sweep_price"]
        result["sweep_type"] = sweep["sweep_type"]
        result["sweep_swing_index"] = sweep["sweep_swing_index"]
        result["sweep_swing_type"] = sweep["sweep_swing_type"]
        if sweep.get("linked_bos_candle") is not None:
            result["linked_bos_candle"] = sweep["linked_bos_candle"]
            result["linked_bos_direction"] = sweep.get("linked_bos_direction")
            result["linked_bos_score"] = sweep.get("linked_bos_score")

    # 10. Score Engine
    scoring = score_setup(result)
    result["scoring"] = scoring

    # Remove None/empty entries (keep scoring even if empty)
    result = {k: v for k, v in result.items()
              if (v is not None and v != []) or k == "scoring"}
    return result
