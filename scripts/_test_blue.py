"""Verify blue/black candles — scan ALL pixels for blue, count candle bodies."""
import asyncio, json
from urllib.parse import quote
from playwright.async_api import async_playwright

OVERRIDES = {
    "mainSeriesProperties.candleStyle.upColor": "#2962ff",
    "mainSeriesProperties.candleStyle.downColor": "#1a1a1a",
    "mainSeriesProperties.candleStyle.borderUpColor": "#2962ff",
    "mainSeriesProperties.candleStyle.borderDownColor": "#1a1a1a",
    "mainSeriesProperties.candleStyle.wickUpColor": "#2962ff",
    "mainSeriesProperties.candleStyle.wickDownColor": "#1a1a1a",
}

URL = (
    "https://s.tradingview.com/widgetembed/"
    "?symbol=OANDA:XAUUSD&interval=5"
    "&hidesidetoolbar=1&theme=light&style=1"
    "&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true"
    f"&overrides={quote(json.dumps(OVERRIDES))}"
)

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)

        # Get the main chart canvas and screenshot ONLY it
        canvases = await page.query_selector_all("canvas")
        main = canvases[0]  # main chart canvas
        await main.screenshot(path="tv_main_canvas.png")

        from PIL import Image
        import numpy as np
        img = Image.open("tv_main_canvas.png").convert("RGB")
        arr = np.array(img)
        total = arr.shape[0] * arr.shape[1]

        # Broad blue detection (any blue-ish, including lighter blues)
        for name, mask in [
            ("Blue (#2962ff-ish)", (arr[:,:,0] < 100) & (arr[:,:,1] > 80) & (arr[:,:,2] > 180)),
            ("Dark blue", (arr[:,:,0] < 80) & (arr[:,:,1] > 60) & (arr[:,:,2] > 120)),
            ("Black (<60)", np.all(arr < 60, axis=2)),
            ("Red-ish", (arr[:,:,0] > 150) & (arr[:,:,1] < 100) & (arr[:,:,2] < 100)),
            ("Green-ish", (arr[:,:,0] < 100) & (arr[:,:,1] > 120) & (arr[:,:,2] < 130)),
        ]:
            count = int(np.sum(mask))
            print(f"{name}: {count} px ({count/total*100:.2f}%)")

        # Find unique colors in chart area
        chart = arr[100:600, 100:900].reshape(-1, 3)
        colors, counts = np.unique(chart, axis=0, return_counts=True)
        top = sorted(zip(counts, colors), reverse=True)[:10]
        print("\nTop 10 colors in chart area:")
        for c, col in top:
            print(f"  {tuple(col)} — {c} px")

        await browser.close()

asyncio.run(test())
