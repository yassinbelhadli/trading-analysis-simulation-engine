from typing import Dict, Any


def format_be_caption(snapshot: Dict[str, Any], be_price: float) -> str:
    scoring = snapshot.get("scoring", {})
    meta = snapshot.get("metadata", {})
    symbol = meta.get("symbol", "?")
    direction = scoring.get("direction", "BUY")

    icon = "\U0001f6bd" if direction == "BUY" else "\U0001f534"

    lines = [
        "\u26fd Break Even Activated",
        f"{icon} {symbol}",
        f"\U0001f6e1\ufe0f SL moved to {be_price:.2f}",
        "",
        "\U0001f50d Risk Free Trade",
    ]
    return "\n".join(lines)
