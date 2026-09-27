"""CoordMapper — converts data coordinates (price, candle index) to pixel coordinates.

Pure calculation, no dependencies. Used by LayoutEngine before rendering.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .scene import Viewport


@dataclass(frozen=True)
class PixelBounds:
    top: float       # pixel y for highest price
    bottom: float    # pixel y for lowest price
    left: float      # pixel x for first candle
    right: float     # pixel x for last candle
    width: float     = 1200.0
    height: float    = 600.0

    @property
    def candle_width(self) -> float:
        return self.width / max(1, self._count - 1) if hasattr(self, "_count") else 12.0


@dataclass(frozen=True)
class CoordMapper:
    """Maps candle index → x, price → y."""

    viewport: Viewport
    bounds: PixelBounds

    # ── x: candle index → pixel ──
    def x_of(self, candle: int) -> float:
        """Map a candle index to its center x pixel (always inside [left, right])."""
        count = self.viewport.candle_count
        slot = self.bounds.width / max(1, count) if count > 1 else self.bounds.width
        offset = candle - self.viewport.candle_first
        return self.bounds.left + (offset + 0.5) * slot

    def width_of(self, candles: int) -> float:
        """Pixel width span for N candles."""
        count = self.viewport.candle_count
        slot = self.bounds.width / max(1, count) if count > 1 else self.bounds.width
        return candles * slot

    # ── y: price → pixel ──
    def y_of(self, price: float) -> float:
        """Map a price to its pixel y (top = highest price)."""
        rng = self.viewport.price_range
        if rng == 0:
            return self.bounds.top
        ratio = (price - self.viewport.price_min) / rng
        return self.bounds.bottom - ratio * self.bounds.height

    def price_range_px(self, price_high: float, price_low: float) -> float:
        """Pixel height of a price range."""
        return abs(self.y_of(price_high) - self.y_of(price_low))

    # ── Inverse ──
    def price_at(self, y: float) -> float:
        """Inverse: pixel y → price. Useful for hit-testing."""
        ratio = (self.bounds.bottom - y) / self.bounds.height
        return self.viewport.price_min + ratio * self.viewport.price_range

    def candle_at(self, x: float) -> int:
        """Inverse: pixel x → candle index. Useful for hit-testing."""
        count = self.viewport.candle_count
        slot = self.bounds.width / max(1, count) if count > 1 else self.bounds.width
        offset = (x - self.bounds.left) // slot if slot > 0 else 0
        return self.viewport.candle_first + int(offset)
