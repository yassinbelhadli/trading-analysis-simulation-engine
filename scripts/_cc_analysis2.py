"""Check small clusters at bottom + right side."""
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
dark = arr < 100

comps = find_components(dark)
print(f"Total components: {len(comps)}")

# Bottom region (y > 600) — time scale + corner
print("\nClusters in bottom region (y 600-662):")
for y0, x0, y1, x1, npx in comps:
    if y0 > 600 and npx >= 5:
        w, h = x1 - x0 + 1, y1 - y0 + 1
        print(f"  x={x0}-{x1} y={y0}-{y1} size={w}x{h} px={npx}")

# Right side (x > 1000) outside price scale... price scale is x=1029-1099
print("\nClusters right side (x 950-1100, all y):")
for y0, x0, y1, x1, npx in comps:
    if x0 >= 950 and npx >= 5:
        w, h = x1 - x0 + 1, y1 - y0 + 1
        print(f"  x={x0}-{x1} y={y0}-{y1} size={w}x{h} px={npx}")
