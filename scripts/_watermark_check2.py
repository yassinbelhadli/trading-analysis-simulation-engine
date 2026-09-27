"""Check if center grayish pixels form a watermark text blob (e.g. 'XAUUSD')."""
from PIL import Image
import numpy as np

img = Image.open("tv_novolume.png").convert("RGB")
arr = np.array(img)

# Grayish = light gray, low saturation
R = arr[:,:,0].astype(int); G = arr[:,:,1].astype(int); B = arr[:,:,2].astype(int)
sat = np.maximum(np.maximum(R,G),B) - np.minimum(np.minimum(R,G),B)
grayish = (sat < 15) & (R >= 150) & (R < 255) & (B >= 150)
# Exclude grid exact color
grayish &= ~(np.all(arr == (213,213,213), axis=2))

ys, xs = np.where(grayish)
if len(xs):
    print(f"grayish px: {len(xs)}")
    print(f"bbox x={xs.min()}-{xs.max()} y={ys.min()}-{ys.max()}")
    # Analyze rows: text would have dense clusters over ~8-20px height, ~50-100px width
    from collections import Counter
    rowc = Counter(ys)
    print("Rows with >30 grayish px:")
    for y, c in sorted(rowc.items()):
        if c > 30:
            xs_ = xs[ys==y]
            print(f"  y={y}: {c} px, x {xs_.min()}-{xs_.max()}")
else:
    print("No grayish pixels")

# Also check mid-gray (could be the watermark in stronger gray)
grayish2 = (sat < 15) & (R >= 100) & (R < 150)
ys2, xs2 = np.where(grayish2)
print(f"\nmid-gray px (100-150): {len(ys2)}")
if len(ys2):
    print(f"bbox x={xs2.min()}-{xs2.max()} y={ys2.min()}-{ys2.max()}")
