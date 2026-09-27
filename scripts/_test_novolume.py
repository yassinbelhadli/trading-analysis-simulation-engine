"""Test disabled_features URL param to remove volume."""
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

DISABLED = json.dumps([
    "create_volume_indicator_by_default",
    "volume_force_overlay",
])

BASE = (
    "https://s.tradingview.com/widgetembed/"
    "?symbol=OANDA:XAUUSD&interval=5"
    "&hidesidetoolbar=1&theme=light&style=1"
    "&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true"
    f"&overrides={quote(OVERRIDES)}"
    f"&disabled_features={quote(DISABLED)}"
)

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        page.on("pageerror", lambda e: print(f"ERR: {e}"))
        await page.goto(BASE, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)
        await page.screenshot(path="tv_novolume.png")
        await browser.close()

    from PIL import Image
    import numpy as np
    img = Image.open("tv_novolume.png").convert("RGB")
    arr = np.array(img)

    pink = np.sum(np.all(arr == (247,169,167), axis=2))
    teal = np.sum(np.all(arr == (146,210,204), axis=2))
    print(f"Volume pink: {pink} px")
    print(f"Volume teal: {teal} px")

    # Check bottom band
    band = arr[500:670, 5:1029]
    print(f"Bottom band: pink={np.sum(np.all(band==(247,169,167),axis=2))} "
          f"teal={np.sum(np.all(band==(146,210,204),axis=2))}")

    # Candles still there?
    blue = np.sum(np.all(arr == (41,98,255), axis=2))
    print(f"Blue candles: {blue} px")

asyncio.run(test())
