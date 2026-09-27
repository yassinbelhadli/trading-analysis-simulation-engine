"""StructureBuilder — converts BOS/CHoCH/MSS from snapshot into Elements."""

from typing import Dict, List, Any

from ..scene import Element, LayerType, ElementType, BoundingBox, Direction
from ..enums import StructureKind, CollisionPolicy


class StructureBuilder:

    def build(self, snapshot: Dict[str, Any]) -> List[Element]:
        struct = snapshot.get("structure", {})
        elements = []
        candles = snapshot.get("chart", {}).get("ohlc", [])
        last_idx = max(0, len(candles) - 1)

        for src_key, kind in [
            ("bos", StructureKind.BOS),
            ("choch", StructureKind.CHOCH),
            ("mss", StructureKind.MSS),
        ]:
            entry = struct.get(src_key) or struct.get(src_key.upper())
            if not entry or not isinstance(entry, dict):
                continue
            price = entry.get("price") or entry.get("level")
            if price is None:
                continue

            direction = Direction.NEUTRAL
            if isinstance(entry.get("direction"), str):
                d = entry["direction"].upper()
                if d in ("BULLISH", "BUY", "UP"):
                    direction = Direction.BULLISH
                elif d in ("BEARISH", "SELL", "DOWN"):
                    direction = Direction.BEARISH

            label = entry.get("label") or kind.name

            elements.append(Element(
                element_type=ElementType.STRUCTURE,
                layer=LayerType.STRUCTURE,
                bbox=BoundingBox(
                    price_high=price,
                    price_low=price,
                    candle_start=entry.get("start_index", 0),
                    candle_end=entry.get("end_index", last_idx),
                ),
                kind=kind,
                direction=direction,
                label=label,
                priority=3,
                collision_policy=CollisionPolicy.NONE,
                data=entry,
            ))

        return elements
