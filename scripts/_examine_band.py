"""Examine structure of the colored band at chart bottom."""
from PIL import Image
import numpy as np

img = Image.open("tv_original.png").convert("RGB")
arr = np.array(img)

# Row at y=650 — what does the pattern look like?
row = arr[650, :, :]
print("Row y=650 (x 0-120):")
for x in range(0, 120, 3):
    print(f"  x={x}: RGB{tuple(row[x])}")

# Column profile at x=500
col = arr[:, 500, :]
print("\nColumn x=500 (y 500-671):")
for y in range(500, 671, 5):
    print(f"  y={y}: RGB{tuple(col[y])}")

# Count pink/teal per 20px x-band at y 600-670 to see if it's vertical bars
print("\nHorizontal profile at y=600-670:")
band = arr[600:670, :, :]
for x0 in range(0, 1029, 40):
    seg = band[:, x0:x0+40, :]
    pink = np.sum(np.all(seg == (247,169,167), axis=2))
    teal = np.sum(np.all(seg == (146,210,204), axis=2))
    print(f"  x={x0}-{x0+40}: pink={pink} teal={teal}")
