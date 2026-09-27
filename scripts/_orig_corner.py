"""Capture original widget corner (logo area) and analyze colors."""
import asyncio, json
from urllib.parse import quote
from playwright.async_api import async_playwright

OVERRIDES = json.dumps({
    "mainSeriesProperties.candleStyle.upColor": "#2962ff",
    "mainSeriesProperties.candleStyle.downColor": "#1a1a1a",
    "mainSeriesProperties.candleStyle.borderUpColor": "#2962ff",
    "mainSeriesProperties.candleStyle.borderDownColor": "#1a1a1a",
    "mainSeriesProperties.candleStyle.wickUpColor": "#2962ff",
    "mainSeriesProperties.candleStyle.wickDownColor": "#1a1a1a",
})

URL = (
    "https://s.tradingview.com/widgetembed/"
    "?symbol=OANDA:XAUUSD&interval=5"
    "&hidesidetoolbar=1&theme=light&style=1"
    "&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true"
    f"&overrides={quote(OVERRIDES)}"
)

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)
        # NO hiding — full original page
        await page.screenshot(path="tv_original.png")
        await browser.close()

    from PIL import Image
    import numpy as np

    img = Image.open("tv_original.png").convert("RGB")
    arr = np.array(img)

    # Corner logo area (1029-1099, 671-699)
    corner = arr[671:699, 1029:1099]
    colors, counts = np.unique(corner.reshape(-1, 3), axis=0, return_counts=True)
    sorted_idx = np.argsort(counts)[::-1]
    print("Original corner (1029-1099, 671-699):")
    for i in sorted_idx[:8]:
        print(f"  RGB{tuple(colors[i])}: {counts[i]} px")

    # Also check bottom-left of chart for watermark (typical TV watermark spot)
    bl = arr[600:671, 5:300]
    colors2, counts2 = np.unique(bl.reshape(-1, 3), axis=0, return_counts=True)
    sorted2 = np.argsort(counts2)[::-1]
    print("\nChart bottom-left (5-300, 600-671):")
    for i in sorted2[:5]:
        print(f"  RGB{tuple(colors2[i])}: {counts2[i]} px")

    # Check bottom-right of chart area (x 800-1029, y 600-671)
    br = arr[600:671, 800:1029]
    colors3, counts3 = np.unique(br.reshape(-1, 3), axis=0, return_counts=True)
    sorted3 = np.argsort(counts3)[::-1]
    print("\nChart bottom-right (800-1029, 600-671):")
    for i in sorted3[:5]:
        print(f"  RGB{tuple(colors3[i])}: {counts3[i]} px")

    # Save corner crop
    img.crop((1020, 660, 1100, 700)).save("orig_corner.png")

asyncio.run(test())
