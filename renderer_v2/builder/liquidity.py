"""LiquidityBuilder — converts swing highs/lows, PDH/PDL, sweep signals."""

from typing import Dict, List, Any

from ..scene import Element, LayerType, ElementType, BoundingBox, Direction
from ..enums import LiquidityKind, SwingKind, CollisionPolicy


class LiquidityBuilder:

    def build(self, snapshot: Dict[str, Any]) -> List[Element]:
        elements = []
        struct = snapshot.get("structure", {})
        liquid = snapshot.get("liquidity", {}) or {}
        session = snapshot.get("session", {}) or {}
        candles = snapshot.get("chart", {}).get("ohlc", [])
        last_idx = max(0, len(candles) - 1)

        for key, kind, label in [
            ("pdh", LiquidityKind.PDH, "PDH"),
            ("pdl", LiquidityKind.PDL, "PDL"),
        ]:
            price = session.get(key) or liquid.get(key) or struct.get(key)
            if price is not None:
                elements.append(Element(
                    element_type=ElementType.LIQUIDITY,
                    layer=LayerType.LIQUIDITY,
                    bbox=BoundingBox(
                        price_high=float(price),
                        price_low=float(price),
                        candle_start=0,
                        candle_end=last_idx,
                    ),
                    kind=kind,
                    direction=Direction.BEARISH if kind == LiquidityKind.PDH
                              else Direction.BULLISH,
                    label=label,
                    priority=4,
                    collision_policy=CollisionPolicy.NONE,
                ))

        sweep = liquid.get("sweep") or liquid.get("sweep_price") or struct.get("sweep_price")
        if sweep is not None:
            price = float(sweep) if not isinstance(sweep, (int, float)) else sweep
            sweep_type = liquid.get("sweep_type", "").upper()
            direction = Direction.BULLISH if "SELL" in sweep_type else Direction.BEARISH
            elements.append(Element(
                element_type=ElementType.LIQUIDITY,
                layer=LayerType.LIQUIDITY,
                bbox=BoundingBox(
                    price_high=price,
                    price_low=price,
                    candle_start=0,
                    candle_end=last_idx,
                ),
                kind=LiquidityKind.SWEEP,
                direction=direction,
                label="Sweep",
                priority=4,
                collision_policy=CollisionPolicy.NONE,
            ))

        swings = struct.get("swings", [])
        for sw in swings:
            sw_type = (sw.get("type") or "").upper()
            kind_map = {"HH": SwingKind.HH, "HL": SwingKind.HL,
                        "LH": SwingKind.LH, "LL": SwingKind.LL}
            skind = kind_map.get(sw_type)
            if not skind:
                continue
            price = sw.get("price", 0)
            idx = sw.get("index", 0)
            elements.append(Element(
                element_type=ElementType.SWING,
                layer=LayerType.SWINGS,
                bbox=BoundingBox(
                    price_high=price,
                    price_low=price,
                    candle_start=idx,
                    candle_end=idx,
                ),
                kind=skind,
                direction=Direction.BULLISH if skind in (SwingKind.HH, SwingKind.HL)
                          else Direction.BEARISH,
                label=sw_type,
                priority=9,
                collision_policy=CollisionPolicy.NONE,
            ))

        return elements
