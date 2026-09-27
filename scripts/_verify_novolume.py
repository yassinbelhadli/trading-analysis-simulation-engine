"""Full layout verification of tv_novolume.png: clean single-panel TradingView chart."""
from PIL import Image
import numpy as np

img = Image.open("tv_novolume.png").convert("RGB")
arr = np.array(img)
H, W, _ = arr.shape
print(f"Image: {W}x{H}")

# 1) Volume gone?
for name, color in [("pink", (247,169,167)), ("teal", (146,210,204))]:
    mask = np.all(arr == color, axis=2)
    ys, xs = np.where(mask)
    print(f"Volume {name}: {int(np.sum(mask))} px" + (f" bbox x={xs.min()}-{xs.max()} y={ys.min()}-{ys.max()}" if len(xs) else ""))

# 2) Candles present + extent
for name, color in [("blue-candle", (41,98,255)), ("black-candle", (26,26,26))]:
    mask = np.all(arr == color, axis=2)
    ys, xs = np.where(mask)
    if len(xs):
        print(f"{name}: {int(np.sum(mask))} px, bbox x={xs.min()}-{xs.max()}, y={ys.min()}-{ys.max()}")

# 3) Grid present (TradingView grid = (213,213,213) or (200,200,200))
for name, color in [("grid(213)", (213,213,213)), ("grid(200)", (200,200,200))]:
    c = int(np.sum(np.all(arr == color, axis=2)))
    if c:
        print(f"{name}: {c} px")

# 4) Any non-white pixels in the area that USED to be volume (y 560-632)?
band = arr[560:632, 5:1029]
nonwhite = np.sum(np.any(band != (255,255,255), axis=2))
print(f"Non-white px in former-volume area (y560-632): {nonwhite}")

# 5) Full-panel scan for possible logo/watermark/branding text:
#    non-white, non-grid, non-black, non-blue, non-time-label, non-price-label pixels
from collections import Counter
mask_wh = np.all(arr == (255,255,255), axis=2)
mask_grid = np.all(arr == (213,213,213), axis=2)
mask_black = np.all(arr == (26,26,26), axis=2)
mask_blue = np.all(arr == (41,98,255), axis=2)
# exclude chart content region for text scan: time axis area y>640
scan = ~(mask_wh | mask_grid | mask_black | mask_blue)
# Restrict scan to candle area only (x<1029) to find stray text; count colors
ys, xs = np.where(scan)
if len(xs):
    print(f"\nStray pixels in chart area: {len(xs)} px")
    sub = arr[ys, xs]
    cc = Counter(map(tuple, sub))
    for c, n in cc.most_common(12):
        print(f"  RGB{c}: {n}")

# 6) Bottom-right corner (clip area)
corner = arr[633:661, 1029:1100]
colors, counts = np.unique(corner.reshape(-1,3), axis=0, return_counts=True)
idx = np.argsort(counts)[::-1]
print("\nCorner (1029-1100, 633-661):")
for i in idx[:4]:
    print(f"  RGB{tuple(colors[i])}: {counts[i]} px")

# 7) Time scale present (labels at y 642-652)
ts = arr[640:652, 5:1029]
dark = np.sum(np.all(ts == (120,120,120), axis=2))
print(f"Time-scale label pixels (gray 120): {dark}")

# 8) Price scale present (x 1030-1099)
ps = arr[40:670, 1030:1099]
nonwhite = np.sum(np.any(ps != (255,255,255), axis=2))
print(f"Non-white px in price scale: {nonwhite}")
