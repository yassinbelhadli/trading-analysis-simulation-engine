"""Locate red/green pixels (current price line?) and verify time scale labels."""
from PIL import Image
import numpy as np

img = Image.open("tv_novolume.png").convert("RGB")
arr = np.array(img)

for name, color in [("red-price", (242,54,69)), ("green-price", (8,153,129))]:
    mask = np.all(arr == color, axis=2)
    ys, xs = np.where(mask)
    if len(xs):
        print(f"{name}: {int(np.sum(mask))} px, x={xs.min()}-{xs.max()}, y={ys.min()}-{ys.max()}")

# Where exactly along x for red at each y row in chart region (y>38)
mask = np.all(arr == (242,54,69), axis=2)
ys, xs = np.where(mask)
rows = {}
for y, x in zip(ys, xs):
    rows.setdefault(y, []).append(x)
print("\nRed pixel rows (top 8 by count):")
for y, xs_ in sorted(rows.items(), key=lambda kv: -len(kv[1]))[:8]:
    print(f"  y={y}: {len(xs_)} px, x range {min(xs_)}-{max(xs_)}")

mask = np.all(arr == (8,153,129), axis=2)
ys, xs = np.where(mask)
rows = {}
for y, x in zip(ys, xs):
    rows.setdefault(y, []).append(x)
print("\nGreen pixel rows (top 8 by count):")
for y, xs_ in sorted(rows.items(), key=lambda kv: -len(kv[1]))[:8]:
    print(f"  y={y}: {len(xs_)} px, x range {min(xs_)}-{max(xs_)}")

# Time scale: scan y 640-655 for any non-white non-grid
band = arr[640:655, 5:1029]
colors, counts = np.unique(band.reshape(-1,3), axis=0, return_counts=True)
idx = np.argsort(counts)[::-1]
print("\nTime scale area colors (y640-655):")
for i in idx[:8]:
    print(f"  RGB{tuple(colors[i])}: {counts[i]}")

# Check for any 'TradingView' watermark text: dark gray text in center area, big pixels
# Watermark is usually light-gray symbol name at center - scan center for large text blocks
center = arr[100:600, 200:850]
grayish = ((np.abs(center[:,:,0].astype(int)-center[:,:,1])<12) &
           (np.abs(center[:,:,1].astype(int)-center[:,:,2])<12) &
           (center[:,:,0]>150) & (center[:,:,0]<250))
print(f"\nGrayish text pixels in center (possible watermark): {int(np.sum(grayish))}")
