"""Draw Entry / SL / TP trade lines — ● ENTRY ──── style."""

from chart_renderer.draw_utils import FONT_NORM

DARK_GRAY = (100, 105, 115)
GREEN = (0, 200, 83)
RED   = (255, 82, 82)
WHITE = (255, 255, 255)
DARK2 = (22, 28, 42)


def _trade_line(draw, y, color, label, x_start, x_end, clamp, line_width=2):
    """● LABEL ────  dot + text pill + line to right."""
    bb = draw.textbbox((0, 0), label, font=FONT_NORM)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    dot_r = 4
    gap = 4
    pad = 4

    dot_cx = x_start + dot_r
    text_x = dot_cx + dot_r + gap
    pill_left = text_x - pad
    pill_right = text_x + tw + pad
    pill_top = y - th // 2 - pad
    pill_bot = y + th // 2 + pad

    draw.rounded_rectangle([pill_left, pill_top, pill_right, pill_bot],
                           radius=4, fill=DARK2 + (200,))
    draw.text((text_x, y), label, fill=WHITE, font=FONT_NORM, anchor="lm")
    draw.ellipse([(dot_cx - dot_r, y - dot_r), (dot_cx + dot_r, y + dot_r)], fill=color)

    line_start = pill_right + 2
    if line_start < x_end:
        draw.line([(line_start, y), (x_end, y)], fill=color, width=line_width)


def draw_trade(draw, entry_price: float, sl_price: float, tp_price: float,
               direction: str, m, clamp):
    """Draw Entry, SL, TP lines — label + line emerging right."""
    ey = int(m.y_line(entry_price))
    sy = int(m.y_line(sl_price))
    ty = int(m.y_line(tp_price))
    chart_right = clamp[2] - 22

    _trade_line(draw, ey, DARK_GRAY, "ENTRY", m.lx + 45, chart_right, clamp, line_width=2)
    _trade_line(draw, sy, RED,       "SL",    m.lx + 45, chart_right, clamp, line_width=2)
    _trade_line(draw, ty, GREEN,     "TP",    m.lx + 45, chart_right, clamp, line_width=2)
