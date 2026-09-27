"""SNAPSHOT CONTENT TRACE — print full snapshot before rendering, count every
ICT element, and locate where any element disappears:

    Detection (SetupCandidate)
        → Snapshot Mapper (setup_to_snapshot)
        → Renderer Bridge / Renderer V2 (build_scene → Scene)
        → PIL Image (pixel check for ICT colors)

No project modules are modified.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import random

from telegram_bot.commands.debug_smoke import _build_debug_candidate, _DEBUG_SNAPSHOT
from renderer_v2.builder import build_scene
from renderer_v2.layout import layout_scene, PixelBounds
from renderer_v2.backends.pil import PILBackend
from renderer_v2.theme import LIGHT_THEME
from PIL import Image

candidate = _build_debug_candidate()

print("=" * 64)
print("STAGE 1 — DETECTION (SetupCandidate)")
print("=" * 64)
print(f"  symbol={candidate.symbol} tf={candidate.timeframe} dir={candidate.direction}")
print(f"  structure: bos={candidate.structure.bos_detected} "
      f"choch={candidate.structure.choch_detected} "
      f"mss={candidate.structure.mss_detected}")
print(f"  liquidity: sweep={candidate.liquidity.sweep_detected} "
      f"sweep_price={candidate.liquidity.sweep_price}")
print(f"  ob: detected={candidate.ob.ob_detected} type={candidate.ob.ob_type}")
print(f"  fvg: detected={candidate.fvg.fvg_detected} type={candidate.fvg.fvg_type}")
print(f"  pd: premium={candidate.premium_discount.premium_high} "
      f"discount={candidate.premium_discount.discount_low}")
print(f"  session: pdh={candidate.session.pdh} pdl={candidate.session.pdl}")
print(f"  plan: entry={candidate.entry_zone} sl={candidate.stop_loss} "
      f"tp={candidate.take_profit}")
print(f"  reasons: {candidate.reasons}")

print()
print("=" * 64)
print("STAGE 2 — SNAPSHOT MAPPER (setup_to_snapshot)")
print("=" * 64)
snap = _DEBUG_SNAPSHOT
def c(k, v):
    print(f"  {k}: {v}")
c("metadata", snap.get("metadata"))
c("chart.ohlc count", len(snap.get("chart", {}).get("ohlc", [])))
struct = snap.get("structure", {})
c("structure keys", list(struct.keys()))
for key in ("bos", "choch", "mss"):
    entry = struct.get(key)
    c(f"structure.{key}", entry if entry else "MISSING")
liq = snap.get("liquidity", {})
c("liquidity", liq if liq else "EMPTY")
c("session", snap.get("session"))
c("order_blocks", snap.get("order_blocks"))
c("fvg", snap.get("fvg"))
c("drawing", snap.get("drawing"))
c("scoring.reasons", snap.get("scoring", {}).get("reasons"))
c("premium_discount key present?", "premium_discount" in snap)
c("premium_discount", snap.get("premium_discount"))

print()
print("=" * 64)
print("STAGE 3 — RENDERER BRIDGE / RENDERER V2 (build_scene)")
print("=" * 64)
scene = build_scene(snap, LIGHT_THEME)
total_els = sum(len(lt.elements) for lt in scene.layers)
for lt in scene.layers:
    print(f"  layer {lt.type.name}: {len(lt.elements)} elements")
print(f"  total elements: {total_els}")
print(f"  viewport: {scene.viewport}")

print()
print("=" * 64)
print("STAGE 4 — LAYOUT + PIXEL CHECK (PILBackend)")
print("=" * 64)
px = PixelBounds(top=0, bottom=600, left=0, right=1200, width=1200, height=600)
layout = layout_scene(scene, px, LIGHT_THEME)
backend = PILBackend(LIGHT_THEME)
img = backend.render(layout, "backtester/reports/debug_snapshot_trace.png")
print(f"  rendered image: {img.size}")

# Pixel check for ICT object colors (non-background, non-candle/grid)
from PIL import Image as _I
img = img.convert("RGB")
w, h = img.size
counts = {}
for x in range(0, w, 4):
    for y in range(0, h, 4):
        r, g, b = img.getpixel((x, y))
        if (r, g, b) in ((255, 255, 255), (254, 245, 245), (242, 249, 254)):
            continue
        key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
        counts[key] = counts.get(key, 0) + 1
top = sorted(counts.items(), key=lambda kv: -kv[1])[:12]
print(f"  distinct non-bg color buckets (sampled): {len(counts)}")
for (r, g, b), n in top:
    print(f"    RGB~({r},{g},{b}): {n} px")
