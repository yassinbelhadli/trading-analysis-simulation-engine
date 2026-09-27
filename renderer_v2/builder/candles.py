"""CandleBuilder — converts OHLC data into candle elements."""

from typing import Dict, List, Any

from ..scene import Element, LayerType, ElementType, BoundingBox, Direction


class CandleBuilder:
    """Build candle elements from snapshot chart data."""

    def build(self, snapshot: Dict[str, Any]) -> List[Element]:
        candles = snapshot.get("chart", {}).get("ohlc", [])
        elements = []
        for c in candles:
            idx = c.get("index", 0)
            elements.append(Element(
                element_type=ElementType.CANDLE,
                layer=LayerType.CANDLES,
                bbox=BoundingBox(
                    price_high=c.get("high", 0),
                    price_low=c.get("low", 0),
                    candle_start=idx,
                    candle_end=idx,
                ),
                direction=(
                    Direction.BULLISH if c.get("close", 0) >= c.get("open", 0)
                    else Direction.BEARISH
                ),
                priority=9,
                data={"open": c.get("open", 0), "close": c.get("close", 0),
                       "volume": c.get("volume", 0), "time": c.get("time", "")},
            ))
        return elements
