"""OBBuilder — converts Order Block entries from snapshot into Elements."""

from typing import Dict, List, Any

from ..scene import Element, LayerType, ElementType, BoundingBox, Direction
from ..enums import CollisionPolicy


class OBBuilder:

    def build(self, snapshot: Dict[str, Any]) -> List[Element]:
        elements = []
        obs = snapshot.get("order_blocks", [])
        candles = snapshot.get("chart", {}).get("ohlc", [])
        last_idx = max(0, len(candles) - 1)

        for ob in obs:
            direction = Direction.BULLISH if (ob.get("type") or "").upper() in (
                "BULLISH", "BUY") else Direction.BEARISH
            top = float(ob.get("top", 0))
            bottom = float(ob.get("bottom", 0))
            if top == 0 and bottom == 0:
                continue
            if bottom > top:
                top, bottom = bottom, top

            label = ob.get("label") or "OB"
            if ob.get("fresh"):
                label = "Fresh OB"
            elif ob.get("mitigated"):
                label = "OB (mitigated)"

            elements.append(Element(
                element_type=ElementType.ORDER_BLOCK,
                layer=LayerType.ORDER_BLOCK,
                bbox=BoundingBox(
                    price_high=top,
                    price_low=bottom,
                    candle_start=ob.get("anchor_candle", ob.get("candle", 0)),
                    candle_end=last_idx,
                ),
                kind=direction,
                direction=direction,
                label=label,
                priority=2,
                collision_policy=CollisionPolicy.NONE,
                data={"fresh": ob.get("fresh", False),
                      "mitigated": ob.get("mitigated", False),
                      "anchor_candle": ob.get("anchor_candle", 0)},
            ))

        return elements
