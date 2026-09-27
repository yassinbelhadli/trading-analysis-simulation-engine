"""Behavioral proof — Header is data-driven and the chart is clean
(no large Info Card overlay, matching the reference look).

Detects:
  1. Header left text ("SELL XAUUSD | M5 | ...") widens as the real
     symbol/timeframe strings grow -> real data, not demo text.
  2. No Info Card box is drawn in the top-left chart region.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from _qa_render import build_snapshot, SCENARIOS
from renderer_v2 import build_scene, layout_scene
from renderer_v2.layout import PixelBounds
from renderer_v2.backends.pil import PILBackend
from renderer_v2.theme import LIGHT_THEME
import numpy as np

BORDER = (229, 231, 235)


def render_arr(snap):
    scene = build_scene(snap)
    px = PixelBounds(top=0, bottom=600, left=0, right=1200, width=1200, height=600)
    layout = layout_scene(scene, px, LIGHT_THEME)
    img = PILBackend(LIGHT_THEME).render(layout)
    return np.array(img.convert("RGB"))


def card_border_cols(arr):
    """Columns with a tall border-colored run in the old Info Card region."""
    region = arr[44:340, 16:1141]
    border_px = np.all(region == BORDER, axis=2).sum(axis=0)
    return np.where(border_px >= 30)[0]


def header_text_width(arr):
    """Width of dark header text in the header band (below the top edge)."""
    band = arr[6:30, 14:900]
    dark = np.all(band < (90, 90, 90), axis=2)
    cols = np.where(dark.sum(axis=0) > 0)[0]
    return int(cols.max()) + 1 if len(cols) else 0


sc = [s for s in SCENARIOS if s["name"] == "XAUUSD_M5_SELL_flagship"][0]

widths = {}
for sym, tf in [("XAUUSD", "M5"), ("GER40_INDEX", "M15"),
                ("SYMBOL_VERY_LONG_NAME_12345", "H4")]:
    s = build_snapshot(sc)
    s["metadata"]["symbol"] = sym
    s["metadata"]["timeframe"] = tf
    s["scoring"]["score"] = 99.0
    s["scoring"]["confidence_score"] = 99.0
    arr = render_arr(s)
    w = header_text_width(arr)
    widths[(sym, tf)] = w
    print(f"  symbol={sym:<28} tf={tf:<4} header text width={w}")

ws = [v for v in widths.values()]
assert all(v > 0 for v in ws), "header text must be drawn"
assert ws[0] < ws[1] < ws[2], "header must widen as real symbol/tf strings grow"
print("✅ Header fully data-driven: width tracks real symbol/timeframe strings")

# Clean chart: no large Info Card box
s = build_snapshot(sc)
arr = render_arr(s)
cols = card_border_cols(arr)
print(f"  info-card border columns found: {len(cols)}")
assert len(cols) == 0, "no large Info Card box should be drawn (clean chart per reference)"
print("✅ Chart is clean: no large Info Card overlay")

print(f"   {list(widths.items())}")
