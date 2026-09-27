"""FVGBuilder — converts FVG entries from snapshot into Elements."""

from typing import Dict, List, Any

from ..scene import Element, LayerType, ElementType, BoundingBox, Direction
from ..enums import CollisionPolicy


class FVGBuilder:

    def build(self, snapshot: Dict[str, Any]) -> List[Element]:
        elements = []
        fvgs = snapshot.get("fvg", []) or snapshot.get("fvgs", [])
        candles = snapshot.get("chart", {}).get("ohlc", [])
        last_idx = max(0, len(candles) - 1)

        for fvg in fvgs:
            direction = Direction.BULLISH if (fvg.get("type") or "").upper() in (
                "BULLISH", "BUY") else Direction.BEARISH
            top = float(fvg.get("top", 0))
            bottom = float(fvg.get("bottom", 0))
            if top == 0 and bottom == 0:
                continue
            if bottom > top:
                top, bottom = bottom, top

            label = fvg.get("label") or "FVG"
            if fvg.get("mitigated"):
                label = "FVG (filled)"

            elements.append(Element(
                element_type=ElementType.FVG,
                layer=LayerType.FVG,
                bbox=BoundingBox(
                    price_high=top,
                    price_low=bottom,
                    candle_start=fvg.get("candle", fvg.get("index", 0)),
                    candle_end=last_idx,
                ),
                kind=direction,
                direction=direction,
                label=label,
                priority=2,
                collision_policy=CollisionPolicy.NONE,
                data={"mitigated": fvg.get("mitigated", False)},
            ))

        return elements
