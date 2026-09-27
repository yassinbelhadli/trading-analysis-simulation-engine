"""Check current chart (tv_cc.png) for volume bars + logo colors."""
from PIL import Image
import numpy as np

img = Image.open("tv_cc.png").convert("RGB")
arr = np.array(img)
print(f"Image: {arr.shape}")

# 1) Volume bar colors present?
vol_pink = np.sum(np.all(arr == (247,169,167), axis=2))
vol_teal = np.sum(np.all(arr == (146,210,204), axis=2))
print(f"Volume pink (247,169,167): {vol_pink} px")
print(f"Volume teal (146,210,204): {vol_teal} px")

# Where are they?
for name, color in [("pink", (247,169,167)), ("teal", (146,210,204))]:
    mask = np.all(arr == color, axis=2)
    ys, xs = np.where(mask)
    if len(xs):
        print(f"  {name} bbox: x={xs.min()}-{xs.max()}, y={ys.min()}-{ys.max()}")

# 2) TradingView logo blue (the "T" logo is #2962ff blue or dark blue #131722)
for name, color in [("TV-blue(41,98,255)", (41,98,255)),
                    ("TV-dark(19,23,34)", (19,23,34)),
                    ("TV-gray(120,120,120)", (120,120,120))]:
    mask = np.all(arr == color, axis=2)
    count = int(np.sum(mask))
    if count:
        ys, xs = np.where(mask)
        print(f"{name}: {count} px, bbox x={xs.min()}-{xs.max()}, y={ys.min()}-{ys.max()}")

# 3) Any non-white/non-grid pixels in the bottom-right corner region (clip 633-661, x 1029-1099)
corner = arr[633:661, 1029:1100]
colors, counts = np.unique(corner.reshape(-1,3), axis=0, return_counts=True)
idx = np.argsort(counts)[::-1]
print("\nCorner colors (clip 1029-1100, 633-661):")
for i in idx[:5]:
    print(f"  RGB{tuple(colors[i])}: {counts[i]} px")

# 4) Check the FULL bottom band (clip y 590-633 = volume area?)
band = arr[590:633, 5:1029]
colors3, counts3 = np.unique(band.reshape(-1,3), axis=0, return_counts=True)
idx3 = np.argsort(counts3)[::-1]
print("\nBottom band (clip 590-633, x 5-1029):")
for i in idx3[:6]:
    print(f"  RGB{tuple(colors3[i])}: {counts3[i]} px")
