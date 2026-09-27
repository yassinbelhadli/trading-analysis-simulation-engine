"""Test URL-encoded overrides for blue/black candles."""
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

print(f"URL: {URL[:120]}...")

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        page.on("pageerror", lambda e: print(f"ERR: {e}"))
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)

        await page.screenshot(path="tv_blue_black2.png")

        # Analyze colors
        from PIL import Image
        import numpy as np
        img = Image.open("tv_blue_black2.png").convert("RGB")
        arr = np.array(img)
        chart = arr[50:650, 50:1000]
        blue = np.sum((chart[:,:,0] < 80) & (chart[:,:,1] > 100) & (chart[:,:,2] > 200))
        green = np.sum((chart[:,:,0] < 80) & (chart[:,:,1] > 150) & (chart[:,:,2] < 120))
        red = np.sum((chart[:,:,0] > 200) & (chart[:,:,1] < 80) & (chart[:,:,2] < 80))
        black = np.sum(np.all(chart < 60, axis=2))
        total = chart.shape[0] * chart.shape[1]
        print(f"Blue: {blue/total*100:.2f}% | Green: {green/total*100:.2f}% | "
              f"Red: {red/total*100:.2f}% | Black: {black/total*100:.2f}%")

        await browser.close()

asyncio.run(test())
