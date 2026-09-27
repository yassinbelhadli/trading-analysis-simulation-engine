"""Draw Order Blocks on the chart."""

from typing import Optional, Dict

from chart_renderer.draw_utils import draw_label, FONT_SMALL, FONT_NORM

OB_BULL = (37, 99, 235)
OB_BEAR = (147, 51, 234)


def draw_ob(draw, ob: dict, m, clamp):
    """Draw an order block rectangle with label."""
    if not ob:
        return
    top = ob.get("top")
    bot = ob.get("bottom")
    if top is None or bot is None:
        return

    is_bull = "Bullish" in ob.get("type", "")
    color = OB_BULL if is_bull else OB_BEAR
    y_top = m.y(max(top, bot))
    y_bot = m.y(min(top, bot))

    x_start = m.clamp_x(m.lx + int(m.cw * 0.05))
    x_end = m.clamp_x(m.lx + int(m.cw * 0.25))

    draw.rectangle([x_start, y_top, x_end, y_bot], fill=color + (20,))
    draw.rectangle([x_start, y_top, x_end, y_bot], outline=color + (40,), width=1)

    cx = (x_start + x_end) // 2
    cy = (y_top + y_bot) // 2
    draw_label(draw, "OB", cx, cy, color + (200,), clamp=clamp, font=FONT_NORM, pad=3)

    if ob.get("fresh"):
        draw_label(draw, "Fresh", cx, cy + 14, color + (200,),
                   clamp=clamp, font=FONT_SMALL, pad=2)
