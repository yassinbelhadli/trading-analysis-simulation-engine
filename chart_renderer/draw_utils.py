"""Shared drawing utilities for all chart overlay modules."""

from typing import Optional, Tuple

try:
    from PIL import ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False


def load_font(size: int):
    for name in ["Segoe UI", "Arial", "DejaVuSans", "LiberationSans"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_BOLD  = load_font(12)
FONT_NORM  = load_font(10)
FONT_SMALL = load_font(8)


def draw_label(draw: ImageDraw.ImageDraw,
               text: str, x: int, y: int,
               bg: Tuple[int, int, int, int],
               fg: Tuple[int, int, int, int] = (255, 255, 255, 255),
               font=None, pad: int = 3,
               anchor: str = "mm",
               clamp: Optional[Tuple[int, int, int, int]] = None):
    """Draw a rounded label box at (x,y) with given anchor.

    anchor: 'mm' = center, 'lm' = left-middle, 'rm' = right-middle
    clamp: (left, top, right, bottom) bounds to keep label visible
    """
    f = font or FONT_NORM
    bb = draw.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]

    if anchor == "mm":
        bx, by = x - tw // 2 - pad, y - th // 2 - pad
        bx2, by2 = x + tw // 2 + pad, y + th // 2 + pad
    elif anchor == "lm":
        bx, by = x, y - th // 2 - pad
        bx2, by2 = x + tw + pad * 2, y + th // 2 + pad
    elif anchor == "rm":
        bx, by = x - tw - pad * 2, y - th // 2 - pad
        bx2, by2 = x, y + th // 2 + pad
    else:
        bx, by = x, y
        bx2, by2 = x + tw + pad * 2, y + th + pad * 2

    # Clamp
    if clamp:
        cl, ct, cr, ccb = clamp
        bw, bh = bx2 - bx, by2 - by
        bx = max(cl, min(bx, cr - bw))
        by = max(ct, min(by, ccb - bh))
        bx2, by2 = bx + bw, by + bh

    draw.rounded_rectangle([bx, by, bx2, by2], radius=3, fill=bg)
    draw.text((bx + pad, by + pad), text, fill=fg, font=f, anchor="la")


def draw_horizontal_line(draw: ImageDraw.ImageDraw,
                         x1: int, x2: int, y: int,
                         color: Tuple[int, int, int, int],
                         width: int = 2):
    """Draw a horizontal line."""
    draw.line([(x1, y), (x2, y)], fill=color, width=width)


def draw_vertical_line(draw, x, y1, y2, color, width=1):
    """Draw a vertical line."""
    draw.line([(x, y1), (x, y2)], fill=color, width=width)


def draw_dashed_horizontal(draw, x1, x2, y, color, width=1, dash=6, gap=4):
    """Draw a dashed horizontal line."""
    total = x2 - x1
    if total <= 0: return
    drawing = True
    x = x1
    while x < x2:
        seg = dash if drawing else gap
        end = min(x + seg, x2)
        if drawing:
            draw.line([(int(x), y), (int(end), y)], fill=color, width=width)
        x = end
        drawing = not drawing
