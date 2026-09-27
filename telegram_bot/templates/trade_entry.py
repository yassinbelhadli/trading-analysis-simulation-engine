"""Template: format entry caption from snapshot dict.

Supports both the old format (drawing.entry.price) and
the new format (drawing.entry_price directly).
"""

from typing import Dict, Any, Optional


def format_entry_caption(snapshot: Dict[str, Any]) -> str:
    meta = snapshot.get("metadata", {})
    scoring = snapshot.get("scoring", {})
    drawing = snapshot.get("drawing", {})
    sess = snapshot.get("session", {})
    exec_data = snapshot.get("execution", {})

    symbol = meta.get("symbol", "?")
    direction = scoring.get("direction", "BUY")
    score = scoring.get("score", 0)
    confidence = scoring.get("confidence_score", 0)
    reasons = scoring.get("reasons", [])
    session_label = sess.get("label")

    # Entry price: support both old (entry.price) and new (entry_price) formats
    entry_price = _val(drawing, "entry_price")
    if entry_price is None:
        entry = drawing.get("entry", {})
        entry_price = entry.get("price") if isinstance(entry, dict) else None
    if entry_price is None:
        entry_price = exec_data.get("entry_zone", {}).get("entry_price")

    sl = _val(drawing, "sl_price") or drawing.get("sl")
    tp_list = drawing.get("tp", [])
    rr = drawing.get("rr")

    icon = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
    direction_arrow = "\U0001f7e8" if direction == "BUY" else "\U0001f7e7"

    lines = [
        f"{icon} {direction} {symbol}",
        f"{direction_arrow} Score {score:.0f}%  |  Confidence {confidence:.0f}%",
    ]
    if session_label:
        lines.append(f"\U0001f3f0 {session_label}")
    lines.append("")

    if reasons:
        lines.append("ICT Checklist:")
        for r in reasons[:7]:
            lines.append(f"\u2705 {r}")
        lines.append("")

    parts = []
    if entry_price:
        parts.append(f"Entry: {entry_price:.2f}")
    if sl:
        parts.append(f"SL: {sl:.2f}")
    if tp_list:
        tps = " / ".join(f"{tp:.2f}" for tp in tp_list)
        parts.append(f"TP: {tps}")
    if rr:
        parts.append(f"RR: {rr:.1f}")

    if parts:
        lines.append("  |  ".join(parts))

    return "\n".join(lines)


def _val(d: dict, key: str) -> Optional[float]:
    v = d.get(key)
    if v is not None:
        try:
            return float(v)
        except (ValueError, TypeError):
            return v
    return None
