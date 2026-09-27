"""Hide top info bar + bottom A/L buttons via JS."""
import asyncio
from playwright.async_api import async_playwright

URL = (
    "https://s.tradingview.com/widgetembed/"
    "?symbol=OANDA:XAUUSD&interval=5"
    "&hidesidetoolbar=1&theme=light&style=1"
    "&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true"
)

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})

        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # Hide all elements by their y-position range
        await page.evaluate("""
            () => {
                const all = document.querySelectorAll('body *');
                all.forEach(el => {
                    const r = el.getBoundingClientRect();
                    // Hide top info bar (y 40-80) — symbol name, OHLC, Vol
                    if (r.y > 38 && r.y < 80) {
                        el.style.display = 'none';
                    }
                    // Hide bottom A/L buttons (y > 630)
                    if (r.y > 630) {
                        // Don't hide the main canvas (it goes to y=671)
                        if (r.width < 200) {
                            el.style.display = 'none';
                        }
                    }
                });
            }
        """)
        await page.wait_for_timeout(500)

        # Clip to remove the top toolbar (timeframe buttons at y=0-38)
        result = await page.screenshot(
            clip={"x": 0, "y": 38, "width": 1100, "height": 662}
        )

        with open("tv_clean2.png", "wb") as f:
            f.write(result)
        import os
        sz = os.path.getsize("tv_clean2.png") / 1024
        print(f"Size: {sz:.1f}KB")

        # Verify with pixel analysis
        from PIL import Image
        import numpy as np
        img = Image.open("tv_clean2.png").convert("RGB")
        arr = np.array(img)

        # Check top of image (should be chart, not info bar)
        top_strip = arr[5:30, 10:900]
        top_white = np.sum(np.all(top_strip > 200, axis=2))
        top_total = top_strip.shape[0] * top_strip.shape[1]
        print(f"Top strip white: {top_white/top_total*100:.1f}%")

        # Check for remnants of text
        dark_in_top = np.sum(np.all(top_strip < 100, axis=2))
        print(f"Dark pixels in top strip: {dark_in_top/top_total*100:.1f}%")

        await browser.close()

asyncio.run(test())
