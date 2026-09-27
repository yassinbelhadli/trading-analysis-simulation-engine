"""Run the real bot capture path and save final image for verification."""
import sys, os, asyncio, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.tv_real_screenshot import capture_chart, _overlay_footer
from PIL import Image
import numpy as np

async def main():
    raw = await capture_chart("XAUUSD", "5")
    final = _overlay_footer(raw, "Gold")
    final.seek(0)
    with open("tv_final.png", "wb") as f:
        f.write(final.read())
    print(f"Saved tv_final.png ({os.path.getsize('tv_final.png')/1024:.1f}KB)")

    img = Image.open("tv_final.png").convert("RGB")
    arr = np.array(img)
    H, W, _ = arr.shape
    print(f"Image: {W}x{H}")

    for name, color in [("pink", (247,169,167)), ("teal", (146,210,204)),
                        ("red", (242,54,69)), ("green", (8,153,129))]:
        c = int(np.sum(np.all(arr == color, axis=2)))
        print(f"{name}: {c} px")

    for name, color in [("blue", (41,98,255)), ("black", (26,26,26))]:
        mask = np.all(arr == color, axis=2)
        ys, xs = np.where(mask)
        if len(xs):
            print(f"{name}: {len(xs)} px, bbox x={xs.min()}-{xs.max()} y={ys.min()}-{ys.max()}")

    # Corner (clip corner region)
    corner = arr[633:661, 1029:1100]
    nw = np.sum(np.any(corner != (255,255,255), axis=2))
    print(f"Corner non-white: {nw}")

    # time labels present
    ts = arr[640:652, 5:1029]
    dark = np.sum(np.all(ts == (15,15,15), axis=2))
    print(f"Time labels (15,15,15): {dark} px")

asyncio.run(main())
