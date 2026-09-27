"""Find remaining TV logo — capture with current logic, scan for text pixels."""
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

HIDE_JS = """
    () => {
        document.querySelectorAll('div, span, button, svg, canvas').forEach(el => {
            const r = el.getBoundingClientRect();
            const cls = (el.className || '').toString();
            if (r.y > 38 && r.y < 82 && r.width < 500 && r.height < 80) {
                el.style.setProperty('display', 'none', 'important');
            }
            if (cls.includes('control-bar')) {
                el.style.setProperty('display', 'none', 'important');
            }
            if (r.x >= 1029 && r.y >= 660) {
                el.style.setProperty('display', 'none', 'important');
            }
        });
    }
"""

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)
        await page.evaluate(HIDE_JS)
        await page.wait_for_timeout(500)
        await page.screenshot(path="tv_current.png",
            clip={"x": 0, "y": 38, "width": 1100, "height": 662})
        await browser.close()

    from PIL import Image
    import numpy as np
    img = Image.open("tv_current.png").convert("RGB")
    arr = np.array(img)

    # Scan bottom-right quadrant in detail (where logos/watermarks live)
    print("Scanning bottom-right region (x 700-1100, y 550-662):")
    for y_block in range(550, 662, 16):
        for x_block in range(700, 1100, 40):
            region = arr[y_block:y_block+16, x_block:x_block+40]
            dark = np.sum(np.all(region < 100, axis=2))
            if dark > 0:
                print(f"  ({x_block}-{x_block+40}, {y_block}-{y_block+16}): {dark} dark px")

    # Also scan whole image for small text clusters
    print("\nChecking corners:")
    corners = {
        "top-left": arr[2:40, 5:300],
        "top-right": arr[2:40, 800:1095],
        "bottom-left": arr[620:660, 5:300],
        "bottom-right": arr[620:660, 800:1095],
    }
    for name, region in corners.items():
        dark = np.sum(np.all(region < 100, axis=2))
        print(f"  {name}: {dark} dark px")

asyncio.run(test())
