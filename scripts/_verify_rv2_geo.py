"""Verify zones (premium/discount tints) and full-width trade lines."""
from PIL import Image
import numpy as np

img = Image.open("backtester/reports/rv2_baseline.png").convert("RGB")
arr = np.array(img)
H, W, _ = arr.shape
chart_l, chart_t, chart_r, chart_b = 6, 34, 1206, 634

def full_width_rows(color, tol=40, min_span=1100):
    rows = []
    for y in range(chart_t, chart_b):
        row = arr[y, chart_l:chart_r]
        mask = np.all(np.abs(row.astype(int) - np.array(color)) <= tol, axis=1)
        runs = 0
        best = 0
        cur = 0
        for m in mask:
            if m:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        if best >= min_span:
            rows.append((y, best))
    return rows

for name, color in [("SL #ef5350", (239, 83, 80)), ("Entry #2962ff", (41, 98, 255)),
                    ("TP #089981", (8, 153, 129))]:
    rows = full_width_rows(color)
    if rows:
        ys = [y for y, _ in rows]
        print(f"{name}: full-width spans at y={min(ys)}..{max(ys)} ({len(rows)} rows)")
    else:
        print(f"{name}: no full-width span found")

# Premium zone: sample just below chart top above eq (y~60), light red/pink tint
prem = arr[60:90, 300:800]
avg = prem.mean(axis=(0, 1))
print(f"Premium zone avg color: {avg.round(1)}  (expect reddish ~ (253,240,240))")

# Discount zone: sample near bottom (y~580), light blue tint
disc = arr[580:610, 300:800]
avg2 = disc.mean(axis=(0, 1))
print(f"Discount zone avg color: {avg2.round(1)}  (expect bluish ~ (247,250,253))")

# Header area should be white with symbol text dark
header = arr[8:30, 16:600]
print(f"Header avg color: {header.mean(axis=(0,1)).round(1)}")

# No watermark: bottom-center area below chart should be white except time axis
bottom = arr[636:660, 100:600]
print(f"Below-chart avg color: {bottom.mean(axis=(0,1)).round(1)} (expect ~white)")
