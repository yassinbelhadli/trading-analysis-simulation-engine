"""Connected-component analysis to locate all text clusters."""
import asyncio, json
from urllib.parse import quote
from playwright.async_api import async_playwright
import numpy as np
from scipy import ndimage

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
        await page.screenshot(path="tv_cc.png",
            clip={"x": 0, "y": 38, "width": 1100, "height": 662})
        await browser.close()

    from PIL import Image
    img = Image.open("tv_cc.png").convert("L")
    arr = np.array(img)
    dark = arr < 100

    # Label connected components (4-connectivity)
    structure = np.ones((3, 3), dtype=int)
    labels, n = ndimage.label(dark, structure=structure)

    # Find components in bottom half + right side (where logo would be)
    print("Text clusters (y > 500 in clip):")
    for i in range(1, n + 1):
        ys, xs = np.where(labels == i)
        if len(xs) < 20:
            continue
        x0, x1 = xs.min(), xs.max()
        y0, y1 = ys.min(), ys.max()
        w, h = x1 - x0 + 1, y1 - y0 + 1
        if y0 > 500 and w > 15 and h > 8:
            print(f"  x={x0}-{x1} y={y0}-{y1} size={w}x{h} pixels={len(xs)}")

asyncio.run(test())
