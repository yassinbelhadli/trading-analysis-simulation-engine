"""Look for the faint light-gray TradingView watermark on the chart."""
import numpy as np
from collections import deque

def find_components(dark_mask):
    h, w = dark_mask.shape
    visited = np.zeros_like(dark_mask, dtype=bool)
    components = []
    for y in range(h):
        for x in range(w):
            if dark_mask[y, x] and not visited[y, x]:
                q = deque([(y, x)])
                visited[y, x] = True
                ys, xs = [], []
                while q:
                    cy, cx = q.popleft()
                    ys.append(cy); xs.append(cx)
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and dark_mask[ny, nx] and not visited[ny, nx]:
                                visited[ny, nx] = True
                                q.append((ny, nx))
                components.append((min(ys), min(xs), max(ys), max(xs), len(ys)))
    return components

from PIL import Image
img = Image.open("tv_cc.png").convert("L")
arr = np.array(img)

# Watermark is usually light gray (~180-230). Find "medium" gray text
# that's NOT background (255) and NOT chart lines
for threshold in [220, 200, 180, 160]:
    mask = (arr < threshold) & (arr > 120)  # medium gray, not white bg
    comps = find_components(mask)
    big = [c for c in comps if c[4] > 100 and (c[2]-c[0]+1) > 20 and (c[3]-c[1]+1) > 30]
    if big:
        print(f"Threshold <{threshold}: {len(big)} large gray clusters:")
        for y0, x0, y1, x1, npx in big[:15]:
            print(f"  x={x0}-{x1} y={y0}-{y1} size={x1-x0+1}x{y1-y0+1} px={npx}")
    else:
        print(f"Threshold <{threshold}: no large gray clusters")

# Also check the chart center specifically (x 300-800, y 200-450) for watermark text
center = arr[150:500, 300:800]
# Sample unique gray levels
vals, counts = np.unique(center, return_counts=True)
print("\nUnique pixel values in chart center (top 15 by count):")
sorted_idx = np.argsort(counts)[::-1][:15]
for i in sorted_idx:
    print(f"  value={vals[i]}: {counts[i]} px")
