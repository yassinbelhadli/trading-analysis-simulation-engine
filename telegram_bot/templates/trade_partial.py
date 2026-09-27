from typing import Dict, Any


def format_partial_caption(snapshot: Dict[str, Any],
                           partial_price: float,
                           partial_pnl: float,
                           remaining_r: Optional[float] = None) -> str:
    scoring = snapshot.get("scoring", {})
    meta = snapshot.get("metadata", {})
    symbol = meta.get("symbol", "?")
    direction = scoring.get("direction", "BUY")

    lines = [
        f"\u2702 TP1 HIT",
        f"{'\U0001f7e2' if direction == 'BUY' else '\U0001f534'} {symbol}",
        f"\U0001f4b0 +${partial_pnl:.2f} Locked",
    ]
    if remaining_r is not None:
        lines.append(f"\U0001f3c3 Runner Active  ({remaining_r:.1f}R remaining)")
    else:
        lines.append("\U0001f3c3 Runner Active")

    return "\n".join(lines)
