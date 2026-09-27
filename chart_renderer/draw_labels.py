"""Draw swing labels (HH/HL/LH/LL) and liquidity labels on the chart."""

from typing import List, Dict
from chart_renderer.draw_utils import draw_label, FONT_SMALL, FONT_NORM

PINK  = (233, 30, 99)
CYAN  = (0, 188, 212)
GOLD  = (255, 215, 0)
DARK2 = (22, 28, 42)
WHITE = (255, 255, 255)


def draw_swing(draw, swing: dict, m, clamp):
    """Draw a single swing label (HH/HL/LH/LL) at its candle position."""
    if not swing:
        return
    price = swing.get("price")
    stype = swing.get("type", "")
    idx = swing.get("index")
    if price is None or idx is None:
        return

    y = int(m.y_line(price))
    x = int(m.x(idx))
    above = stype in ("HH", "LH")
    off = -8 if above else 8

    draw_label(draw, stype, x, y + off,
               DARK2 + (200,), WHITE, clamp=clamp, font=FONT_SMALL, pad=2)


def draw_swings(draw, swings: List[Dict], m, clamp):
    """Draw last 2 swings."""
    for sw in (swings[-2:] if len(swings) > 2 else swings):
        draw_swing(draw, sw, m, clamp)


def draw_sweep(draw, sweep_price: float, sweep_type: str, m, clamp):
    """Draw sweep / liquidity label."""
    if sweep_price is None:
        return
    y = int(m.y_line(sweep_price))
    text = f"Sweep {sweep_type}" if sweep_type else "Sweep"
    draw_label(draw, text, m.lx + int(m.cw * 0.5), y,
               PINK + (180,), WHITE, clamp=clamp, font=FONT_SMALL, pad=2)


def draw_pdh_pdl(draw, pdh: float, pdl: float, m, clamp):
    """Draw PDH / PDL level labels."""
    if pdh is not None:
        draw_label(draw, "PDH", m.lx + m.cw - 20, m.y(pdh),
                   CYAN + (180,), WHITE, clamp=clamp, font=FONT_SMALL, pad=2, anchor="rm")
    if pdl is not None:
        draw_label(draw, "PDL", m.lx + m.cw - 20, m.y(pdl),
                   (255, 152, 0, 180), WHITE, clamp=clamp, font=FONT_SMALL, pad=2, anchor="rm")
