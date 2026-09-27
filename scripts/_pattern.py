"""Understand red/green pixel pattern: are these horizontal dashed lines or something else?"""
from PIL import Image
import numpy as np

img = Image.open("tv_novolume.png").convert("RGB")
arr = np.array(img)

# Examine red row y=326 in detail
for color, name in [((242,54,69),"red"), ((8,153,129),"green")]:
    mask = np.all(arr == color, axis=2)
    ys, xs = np.where(mask)
    rows = {}
    for y, x in zip(ys, xs):
        rows.setdefault(y, []).append(x)
    print(f"=== {name} ===")
    print(f"distinct rows: {len(rows)}")
    # Check: is each row a contiguous segment or many small dashes?
    for y in sorted(rows)[:6]:
        xs_ = sorted(rows[y])
        gaps = sum(1 for i in range(1, len(xs_)) if xs_[i]-xs_[i-1] > 3)
        print(f"  y={y}: {len(xs_)} px, {gaps} gaps, x {xs_[0]}-{xs_[-1]}")
    print()

# Vertical structure: at x=500, which y rows have red/green?
col = arr[:, 500]
print("At x=500, rows with red/green:")
for y in range(40, 660):
    c = tuple(col[y])
    if c in ((242,54,69),(8,153,129)):
        print(f"  y={y}: {c}")
