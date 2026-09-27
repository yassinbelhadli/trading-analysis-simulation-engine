"""Locate the colored regions (247,169,167) and (146,210,204)."""
from PIL import Image
import numpy as np

img = Image.open("tv_original.png").convert("RGB")
arr = np.array(img)

for name, color in [("light-red(247,169,167)", (247,169,167)),
                    ("teal(146,210,204)", (146,210,204))]:
    mask = np.all(arr == color, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        print(f"{name}: none")
        continue
    print(f"{name}: {len(xs)} px")
    print(f"  bbox x={xs.min()}-{xs.max()}, y={ys.min()}-{ys.max()}")

# Check row profile: how many colored px per y-band
for y0 in range(0, 700, 50):
    band = arr[y0:y0+50]
    pink = np.sum(np.all(band == (247,169,167), axis=2))
    teal = np.sum(np.all(band == (146,210,204), axis=2))
    if pink or teal:
        print(f"y={y0}-{y0+50}: pink={pink} teal={teal}")
