"""Map price → y-pixel and candle-index → x-pixel on the chart area."""

from typing import Optional


class CoordMapper:
    """Converts price levels and candle indices to exact pixel coordinates."""

    def __init__(self, chart_left: int, chart_top: int,
                 chart_width: int, chart_height: int,
                 price_high: float, price_low: float,
                 candle_start: int, candle_end: int):
        self.lx = chart_left
        self.ty = chart_top
        self.cw = chart_width
        self.ch = chart_height
        self.ph = price_high
        self.pl = price_low
        self.cs = candle_start
        self.ce = candle_end

    @classmethod
    def from_ranges(cls, chart_left: int, chart_top: int,
                    chart_width: int, chart_height: int,
                    price_high: float, price_low: float,
                    total_candles: int, visible_end: int,
                    visible_count: int = None) -> "CoordMapper":
        """Create mapper with auto-calculated candle range."""
        if visible_count:
            cs = max(0, visible_end - visible_count)
        else:
            cs = 0
        return cls(chart_left, chart_top, chart_width, chart_height,
                   price_high, price_low, cs, visible_end)

    def y(self, price: float) -> int:
        """Price → y pixel (top of chart = high price)."""
        frac = (price - self.pl) / (self.ph - self.pl)
        return int(self.ty + self.ch - frac * self.ch)

    def x(self, candle_index: int) -> int:
        """Candle index → x pixel."""
        if self.cs >= self.ce:
            return self.lx
        frac = (candle_index - self.cs) / (self.ce - self.cs)
        return int(self.lx + frac * self.cw)

    def y_line(self, price: float) -> float:
        """Float version for line drawing precision."""
        frac = (price - self.pl) / (self.ph - self.pl)
        return self.ty + self.ch - frac * self.ch

    def price_at_y(self, y: int) -> float:
        """Reverse: y pixel → price."""
        frac = (self.ty + self.ch - y) / self.ch
        return self.pl + frac * (self.ph - self.pl)

    def clamp_x(self, x: int, margin: int = 4) -> int:
        return max(self.lx + margin, min(x, self.lx + self.cw - margin))

    def clamp_y(self, y: int, margin: int = 4) -> int:
        return max(self.ty + margin, min(y, self.ty + self.ch - margin))
