"""Identify the gray cluster at (1030-1076, 570-593)."""
from PIL import Image
import numpy as np

img = Image.open("tv_cc.png").convert("RGB")
arr = np.array(img)

region = arr[568:596, 1028:1078]
colors, counts = np.unique(region.reshape(-1, 3), axis=0, return_counts=True)
sorted_idx = np.argsort(counts)[::-1]
print("Colors in region (1030-1076, 570-593):")
for i in sorted_idx[:10]:
    print(f"  RGB{tuple(colors[i])}: {counts[i]} px")

# Check if it's text-like: dark-on-light pattern
print(f"\nRegion size: {region.shape}")

# Find bounding box of the non-white pixels
mask = np.any(region < 250, axis=2)
ys, xs = np.where(mask)
if len(xs):
    print(f"Non-white pixels: {len(xs)}")
    print(f"BBox: x={xs.min()+1028}-{xs.max()+1028}, y={ys.min()+568}-{ys.max()+568}")

# Save the crop for reference
img.crop((1028, 568, 1078, 596)).save("gray_cluster_crop.png")
print("Crop saved: gray_cluster_crop.png")
