"""Hide top info text + bottom A/L buttons with !important."""
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

        # Force-hide via !important style injection
        await page.evaluate("""
            () => {
                const all = document.querySelectorAll('div, span, button');
                all.forEach(el => {
                    const text = el.textContent.trim();
                    const r = el.getBoundingClientRect();
                    // Top info area (y 38-80): symbol name, OHLC, Vol
                    if (r.y > 38 && r.y < 82 && r.width < 1100) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                    // Bottom A/L buttons and controls (y > 630, small width)
                    if (r.y > 630 && r.width < 100 && r.height < 40) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                });
            }
        """)
        await page.wait_for_timeout(500)

        result = await page.screenshot(
            clip={"x": 0, "y": 38, "width": 1100, "height": 662}
        )

        with open("tv_clean4.png", "wb") as f:
            f.write(result)
        import os
        sz = os.path.getsize("tv_clean4.png") / 1024
        print(f"Size: {sz:.1f}KB")

        # Check A/L button area
        from PIL import Image
        import numpy as np
        img = Image.open("tv_clean4.png").convert("RGB")
        arr = np.array(img)
        button_area = arr[600:635, 1025:1095]
        dark = np.sum(np.all(button_area < 100, axis=2))
        total = button_area.shape[0] * button_area.shape[1]
        print(f"A/L area dark pixels: {dark}/{total} = {dark/total*100:.1f}%")

        await browser.close()

asyncio.run(test())
