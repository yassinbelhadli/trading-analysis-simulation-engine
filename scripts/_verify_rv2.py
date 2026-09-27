"""Verify new renderer output: candles, grid, trade lines, info card, current price pill."""
from PIL import Image
import numpy as np

img = Image.open("backtester/reports/rv2_baseline.png").convert("RGB")
arr = np.array(img)
H, W, _ = arr.shape
print(f"Image: {W}x{H}")

def count(color, name):
    mask = np.all(arr == color, axis=2)
    ys, xs = np.where(mask)
    if len(xs):
        print(f"{name}: {len(xs)} px, x={xs.min()}-{xs.max()}, y={ys.min()}-{ys.max()}")
    else:
        print(f"{name}: 0 px")
    return mask

# Candles
count((41, 98, 255), "candle-bull blue #2962ff")
count((26, 26, 26), "candle-bear black #1a1a1a")

# Grid (light)
count((238, 240, 242), "grid #eef0f2")

# Trade lines
count((41, 98, 255), "entry blue (overlap w/ candles)")
count((239, 83, 80), "SL red #ef5350")
count((8, 153, 129), "TP green #089981")

# Structure colors
count((30, 136, 229), "BOS blue #1e88e5")
count((251, 192, 45), "CHoCH amber #fbc02d")
count((123, 31, 162), "MSS purple #7b1fa2")
count((251, 140, 0), "liquidity orange #fb8c00")

# Check top-left region for info card (white box w/ border)
card_region = arr[44:280, 16:260]
white_card = np.all(card_region == (255, 255, 255), axis=2)
border_color = (229, 231, 235)
border_px = np.sum(np.all(card_region == border_color, axis=2))
print(f"\nInfo card region: white={int(np.sum(white_card))} px, border={int(border_px)} px")

# Current price pill: blue pill on right axis area (x > 1200, i.e. chart_r=1206..1284)
right_axis = arr[40:640, 1206:1284]
blue_pill = np.sum(np.all(right_axis == (41, 98, 255), axis=2))
print(f"Right axis blue px (current price pill): {blue_pill}")

# Check no watermark center (faint text should not exist; center should be candle/grid only)
center = arr[300:400, 400:800]
nonwhite = np.sum(np.any(center != (255, 255, 255), axis=2))
print(f"Center non-white px: {nonwhite}")

# Direction badge in header (red SELL pill top-right)
header = arr[8:32, 1000:1270]
red_header = np.sum(np.all(header == (239, 83, 80), axis=2))
print(f"Header SELL badge red px: {red_header}")
