"""Connected-component analysis without scipy."""
import numpy as np
from collections import deque

def find_components(dark_mask):
    """Simple 8-connectivity labeling via BFS flood fill."""
    h, w = dark_mask.shape
    visited = np.zeros_like(dark_mask, dtype=bool)
    components = []
    for y in range(h):
        for x in range(w):
            if dark_mask[y, x] and not visited[y, x]:
                # BFS
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

print("Finding components...")
comps = find_components(dark)
print(f"Total components: {len(comps)}")

# Text-like clusters in the bottom area (y > 500)
print("\nLarge clusters (y > 500):")
for y0, x0, y1, x1, npx in comps:
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if y0 > 500 and npx > 30 and w > 12 and h > 8:
        print(f"  x={x0}-{x1} y={y0}-{y1} size={w}x{h} px={npx}")

print("\nAll large clusters:")
for y0, x0, y1, x1, npx in comps:
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if npx > 200 and w > 30 and h > 10:
        print(f"  x={x0}-{x1} y={y0}-{y1} size={w}x{h} px={npx}")
