"""TradeBuilder — converts trade setup / drawing data into Elements."""

from typing import Dict, List, Any

from ..scene import Element, LayerType, ElementType, BoundingBox, Direction
from ..enums import TradeKind, CollisionPolicy


class TradeBuilder:

    def build(self, snapshot: Dict[str, Any]) -> List[Element]:
        elements = []
        drawing = snapshot.get("drawing", {}) or {}
        trade = snapshot.get("trade", {}) or {}
        candles = snapshot.get("chart", {}).get("ohlc", [])
        last_idx = max(0, len(candles) - 1)

        direction = Direction.BULLISH
        raw_dir = (drawing.get("buy_sell") or trade.get("direction") or "").upper()
        if raw_dir in ("SELL", "BEARISH"):
            direction = Direction.BEARISH

        entry_price = float(drawing.get("entry_price") or trade.get("entry_price") or 0)
        sl_price = float(drawing.get("sl_price") or trade.get("sl_price") or 0)

        def add_trade(kind: TradeKind, key: str, label: str, priority: int):
            price = drawing.get(key) or trade.get(key)
            if price is None:
                price = trade.get(f"{key}_price")
            if price is None:
                return
            price = float(price)
            price_str = f"{price:.2f}" if price == int(price) else f"{price:.2f}"
            elements.append(Element(
                element_type=ElementType.TRADE,
                layer=LayerType.TRADES,
                bbox=BoundingBox(
                    price_high=price,
                    price_low=price,
                    candle_start=last_idx - 5,
                    candle_end=last_idx,
                ),
                kind=kind,
                direction=direction,
                label=f"{label} {price_str}",
                priority=priority,
                collision_policy=CollisionPolicy.NONE,
                data={"price": price},
            ))

        add_trade(TradeKind.ENTRY, "entry_price", "Entry", 1)
        add_trade(TradeKind.STOP_LOSS, "sl_price", "SL", 1)

        tp_prices = drawing.get("tp", []) or trade.get("tp_prices", [])
        if isinstance(tp_prices, list):
            for i, tp in enumerate(tp_prices):
                if tp:
                    tp = float(tp)
                    rr = ""
                    if entry_price and sl_price:
                        risk = abs(entry_price - sl_price)
                        if risk > 0:
                            reward = abs(tp - entry_price)
                            rr = f" (R:{reward/risk:.1f})"
                    elements.append(Element(
                        element_type=ElementType.TRADE,
                        layer=LayerType.TRADES,
                        bbox=BoundingBox(
                            price_high=tp, price_low=tp,
                            candle_start=last_idx - 5, candle_end=last_idx,
                        ),
                        kind=TradeKind.TAKE_PROFIT,
                        direction=direction,
                        label=f"TP {i+1}{rr}",
                        priority=1,
                        collision_policy=CollisionPolicy.NONE,
                        data={"price": tp},
                    ))
        elif isinstance(tp_prices, (int, float)):
            elements.append(Element(
                element_type=ElementType.TRADE,
                layer=LayerType.TRADES,
                bbox=BoundingBox(
                    price_high=float(tp_prices), price_low=float(tp_prices),
                    candle_start=last_idx - 5, candle_end=last_idx,
                ),
                kind=TradeKind.TAKE_PROFIT,
                direction=direction,
                label="TP",
                priority=1,
                collision_policy=CollisionPolicy.NONE,
                data={"price": float(tp_prices)},
            ))

        add_trade(TradeKind.EXIT, "exit_price", "Exit", 1)
        add_trade(TradeKind.PARTIAL, "partial_price", "Partial", 1)
        add_trade(TradeKind.BREAK_EVEN, "be_price", "BE", 1)

        return elements
