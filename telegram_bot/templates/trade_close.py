from typing import Dict, Any, Optional


def format_close_caption(snapshot: Dict[str, Any],
                         exit_price: float, realized_pnl: float,
                         realized_r: float, exit_reason: str,
                         duration: Optional[str] = None,
                         mfe: Optional[float] = None,
                         mae: Optional[float] = None,
                         be_activated: bool = False,
                         partial_pnl: Optional[float] = None) -> str:
    scoring = snapshot.get("scoring", {})
    meta = snapshot.get("metadata", {})

    symbol = meta.get("symbol", "?")
    direction = scoring.get("direction", "BUY")
    is_win = realized_pnl >= 0
    is_tp = "TP" in exit_reason
    is_sl = "SL" in exit_reason

    direction_icon = "\U0001f7e2" if direction == "BUY" else "\U0001f534"

    if is_win and is_tp:
        label = "\U0001f389 TP HIT"
    elif is_sl:
        label = "\U0001f6ab SL HIT"
    else:
        label = f"\U0001f4cc Close"

    pnl_icon = "\U0001f4b0" if is_win else "\U0001f53d"
    pnl_sign = "+" if is_win else ""
    rr_label = f"{pnl_sign}{realized_r:.2f}R" if realized_r else ""

    lines = [
        f"{label}",
        f"{direction_icon} {symbol}",
        f"{pnl_icon} {pnl_sign}${realized_pnl:.2f}  ({rr_label})",
    ]
    if duration:
        lines.append(f"\u23f1 {duration}")
    lines.append("")

    if mfe is not None:
        lines.append(f"\U0001f4c8 MFE: +{mfe:.2f}R")
    if mae is not None:
        lines.append(f"\U0001f4c9 MAE: -{mae:.2f}R")
    if be_activated:
        lines.append("\u26fd BE Activated")
    if partial_pnl:
        lines.append(f"\u2702 Partial: +${partial_pnl:.2f}")

    return "\n".join(lines)
