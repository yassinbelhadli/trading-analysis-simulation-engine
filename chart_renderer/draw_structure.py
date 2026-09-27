"""Draw BOS / CHoCH / MSS structure lines on the chart."""

from typing import Optional, Dict

from chart_renderer.draw_utils import draw_label, FONT_NORM

BOS_CLR  = (6, 182, 212)
CH_CLR   = (245, 158, 11)
MSS_CLR  = (236, 72, 153)


def draw_structure(draw, key: str, label: str, color, data: Optional[Dict], m, clamp):
    """Draw a BOS/CHoCH/MSS split line at the structure's price level.

    The line spans from start_index to end_index.
    Label is placed above the line at the midpoint.
    """
    if not data or not isinstance(data, dict):
        return
    price = data.get("price")
    if price is None:
        return

    ly = int(m.y_line(price))

    # Default to visible range if indices not given
    start_idx = data.get("start_index", m.cs)
    end_idx = data.get("end_index", m.ce)
    xs = m.clamp_x(int(m.x(start_idx)))
    xe = m.clamp_x(int(m.x(end_idx)))
    if xs >= xe:
        return

    # Single line at event location, label above it
    # Line from breakout candle to end
    draw.line([(xs, ly), (xe, ly)], fill=color + (220,), width=2)
    # Label directly above the breakout candle
    draw_label(draw, label, xs, ly - 14,
               color + (220,), clamp=clamp, font=FONT_NORM, pad=3)
