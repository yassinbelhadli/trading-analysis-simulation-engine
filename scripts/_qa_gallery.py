"""Build an HTML gallery + contact sheet of all QA renders, and check for
edge clipping (any content bleeding off the image border)."""
import os, sys, glob, math
from PIL import Image, ImageDraw
import numpy as np

OUT = "backtester/reports/qa"
pngs = sorted(glob.glob(os.path.join(OUT, "*.png")))
pngs = [p for p in pngs if "_contact" not in p]

# ── edge clipping check ─────────────────────────────────────────────
clipped = []
for p in pngs:
    arr = np.array(Image.open(p).convert("RGB"))
    h, w, _ = arr.shape
    bg = np.array([255, 255, 255])
    # outermost 2px border (top, bottom, left, right)
    borders = [arr[0:2, :, :], arr[h-2:h, :, :], arr[:, 0:2, :], arr[:, w-2:w, :]]
    for i, b in enumerate(borders):
        non_bg = int(np.sum(np.any(b != bg, axis=2)))
        if non_bg > 20:
            clipped.append((os.path.basename(p), i, non_bg))

if clipped:
    print(f"⚠ {len(clipped)} images with border content (potential clipping):")
    for name, edge, n in clipped[:20]:
        print(f"  {name} edge#{edge} {n}px")
else:
    print("✅ No border clipping detected.")

# ── contact sheet ────────────────────────────────────────────────────
cols = 4
th_w, th_h = 321, 165  # 1284x660 / 4
imgs = []
for p in pngs:
    im = Image.open(p).convert("RGB")
    im.thumbnail((th_w, th_h), Image.LANCZOS)
    imgs.append(im)

rows = math.ceil(len(imgs) / cols)
pad = 6
sheet = Image.new("RGB", (cols * th_w + (cols + 1) * pad,
                          rows * (th_h + 18) + (rows + 1) * pad), (245, 245, 245))
draw = ImageDraw.Draw(sheet)
for i, im in enumerate(imgs):
    r, c = divmod(i, cols)
    x = pad + c * (th_w + pad)
    y = pad + r * (th_h + 18 + pad)
    sheet.paste(im, (x, y))
    name = os.path.basename(pngs[i]).replace(".png", "")
    draw.text((x, y + th_h + 2), name, fill=(40, 40, 40))
sheet.save(os.path.join(OUT, "_contact_sheet.png"))
print(f"Contact sheet: {len(imgs)} thumbs -> {OUT}/_contact_sheet.png")

# ── HTML gallery ─────────────────────────────────────────────────────
rows_html = []
for p in pngs:
    name = os.path.basename(p)
    rows_html.append(
        f'<div class="card"><a href="{name}"><img loading="lazy" src="{name}"></a>'
        f'<div class="cap">{name}</div></div>')
html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Renderer QA — 86 scenarios</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px}
h1{font-size:20px;margin:0 0 6px}.sub{color:#94a3b8;font-size:13px;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}
.card{background:#1e293b;border-radius:10px;padding:10px;border:1px solid #334155}
.card img{width:100%;border-radius:6px;background:#fff}
.cap{font-size:11px;color:#cbd5e1;margin-top:6px;font-family:Consolas,monospace}
</style></head><body>
<h1>Renderer QA — """ + f"{len(pngs)} scenarios" + """</h1>
<div class="sub">BUY/SELL × BOS/CHoCH/MSS × FVG/OB/Sweep × TP1-3 × win/loss × volatility × BTC/XAU/US100/EURUSD × H1/M15 × far levels × edge cases</div>
<div class="grid">""" + "\n".join(rows_html) + "</div></body></html>"
with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print(f"Gallery: {OUT}/index.html")
