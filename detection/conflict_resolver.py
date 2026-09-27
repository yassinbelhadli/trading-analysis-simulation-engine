"""Conflict Resolver — deduplicate signals by break candle with priority hierarchy.

Priority (highest → lowest):
  1. MSS          — Market Structure Shift
  2. CHoCH        — Change of Character
  3. External BOS — break of major swing (HH/LH at range extreme)
  4. Internal BOS — break of minor swing inside range

Within BOS, subtype priority:
  External HH > External LH > Internal HH > Internal HL/LL > Internal LH
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# BOS subtype priority score (higher = more important)
_BOS_SUBTYPE_PRIORITY = {
    ("External", "HH"): 100,
    ("External", "LH"): 90,
    ("External", "HL"): 85,
    ("External", "LL"): 85,
    ("Internal", "HH"): 70,
    ("Internal", "HL"): 65,
    ("Internal", "LL"): 60,
    ("Internal", "LH"): 50,
}

_CONTINUATION_WINDOW = 5  # candles


def _bos_priority(bos_event: Dict) -> int:
    """Return numeric priority for a BOS event (higher = more important)."""
    bos_type = bos_event.get("bos_type", "Internal")
    swing_type = bos_event.get("swing_type", "?")
    key = (bos_type, swing_type)
    base = _BOS_SUBTYPE_PRIORITY.get(key, 40)
    # Within same subtype, higher displacement = higher priority
    disp = bos_event.get("displacement_pct", 0)
    return base + disp


def resolve(swings: List[Dict],
            bos_list: List[Dict],
            choch_list: List[Dict],
            mss_list: List[Dict]) -> Dict:
    """Resolve conflicts across all signal types.

    Returns:
    {
        "bos": [...],     # deduplicated, highest priority per candle
        "choch": [...],   # filtered: no candle with MSS
        "mss": [...],     # unchanged (already highest priority)
        "bos_hidden": [...],  # deduped BOS kept for reference, not for signals
    }
    """
    # Index BOS by break candle
    bos_by_candle: Dict[int, List[Dict]] = {}
    for b in bos_list:
        idx = b["candle_index"]
        bos_by_candle.setdefault(idx, []).append(b)

    # Index CHoCH by break candle
    choch_by_candle: Dict[int, List[Dict]] = {}
    for c in choch_list:
        idx = c["candle_index"]
        choch_by_candle.setdefault(idx, []).append(c)

    # Index MSS by break candle
    mss_by_candle: Dict[int, List[Dict]] = {}
    for m in mss_list:
        idx = m["candle_index"]
        mss_by_candle.setdefault(idx, []).append(m)

    all_candles = set()
    all_candles.update(bos_by_candle.keys())
    all_candles.update(choch_by_candle.keys())
    all_candles.update(mss_by_candle.keys())

    resolved_bos = []
    bos_hidden = []
    resolved_choch = []
    resolved_mss = []

    for idx in sorted(all_candles):
        has_mss = idx in mss_by_candle
        has_choch = idx in choch_by_candle
        has_bos = idx in bos_by_candle

        # MSS is always highest priority
        if has_mss:
            resolved_mss.extend(mss_by_candle[idx])
            # Suppress CHoCH and BOS at same candle
            if has_choch:
                pass  # silently drop
            if has_bos:
                bos_hidden.extend(bos_by_candle[idx])
            continue

        # CHoCH + BOS at same candle: keep CHoCH only
        if has_choch and has_bos:
            resolved_choch.extend(choch_by_candle[idx])
            bos_hidden.extend(bos_by_candle[idx])
            continue

        # CHoCH only
        if has_choch:
            resolved_choch.extend(choch_by_candle[idx])
            continue

        # BOS only — deduplicate to highest priority per candle
        if has_bos:
            candidates = bos_by_candle[idx]
            # Sort by priority descending
            candidates.sort(key=_bos_priority, reverse=True)
            # Keep highest priority
            resolved_bos.append(candidates[0])
            # Hide the rest
            for dup in candidates[1:]:
                dup["hidden_reason"] = f"Dup on candle {idx}: lower priority than primary"
                bos_hidden.append(dup)

    # Mark continuations (BOS within 5 candles of previous same-direction BOS)
    prev_bos_by_dir: Dict[str, int] = {}
    for b in resolved_bos:
        direction = b["direction"]
        prev_idx = prev_bos_by_dir.get(direction)
        b_idx = b["candle_index"]
        if prev_idx is not None and b_idx - prev_idx <= _CONTINUATION_WINDOW:
            b["continuation"] = True
            b["note"] = f"Continuation: {b_idx - prev_idx} candles since last {direction} BOS"
        else:
            b["continuation"] = False
        prev_bos_by_dir[direction] = b_idx

    return {
        "bos": resolved_bos,
        "choch": resolved_choch,
        "mss": resolved_mss,
        "bos_hidden": bos_hidden,
    }
