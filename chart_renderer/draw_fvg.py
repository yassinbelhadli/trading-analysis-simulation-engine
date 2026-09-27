"""Draw Fair Value Gaps on the chart."""

from chart_renderer.draw_utils import draw_label, draw_dashed_horizontal, FONT_NORM, FONT_SMALL

FVG_BULL = (34, 197, 94)
FVG_BEAR = (239, 68, 68)


def draw_fvg(draw, fvg: dict, m, clamp):
    """Draw an FVG rectangle with dashed borders and centered label."""
    if not fvg:
        return
    top = fvg.get("top")
    bot = fvg.get("bottom")
    if top is None or bot is None:
        return

    is_bull = "Bullish" in fvg.get("type", "")
    color = FVG_BULL if is_bull else FVG_BEAR
    y_top = m.y(max(top, bot))
    y_bot = m.y(min(top, bot))

    x_start = m.clamp_x(m.lx + int(m.cw * 0.28))
    x_end = m.clamp_x(m.lx + int(m.cw * 0.48))

    # Border-only dashed FVG — no fill
    draw_dashed_horizontal(draw, x_start, x_end, y_top, color + (60,), width=1)
    draw_dashed_horizontal(draw, x_start, x_end, y_bot, color + (60,), width=1)
    draw.line([(x_start, y_top), (x_start, y_bot)], fill=color + (60,), width=1)
    draw.line([(x_end, y_top), (x_end, y_bot)], fill=color + (60,), width=1)

    cx = (x_start + x_end) // 2
    cy = (y_top + y_bot) // 2
    draw_label(draw, "FVG", cx, cy, color + (200,), clamp=clamp, font=FONT_NORM, pad=3)

    if fvg.get("mitigated"):
        draw_label(draw, "Mit", cx, cy + 14, (19, 23, 34, 200),
                   (255, 255, 255, 200), clamp=clamp, font=FONT_SMALL, pad=2)
