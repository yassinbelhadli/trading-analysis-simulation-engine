"""Safe hiding — only hide small text elements, never the chart container."""
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

        await page.evaluate("""
            () => {
                const hideKeywords = ['Gold Spot', 'U.S. Dollar', 'OANDA', 'Vol',
                                      'Ticks', 'Spread', 'Session'];
                const all = document.querySelectorAll('div, span, button');
                all.forEach(el => {
                    const text = el.textContent.trim();
                    const r = el.getBoundingClientRect();
                    // Only hide small text elements in the info bar area (y 38-80)
                    if (r.y > 38 && r.y < 82 && r.width < 500) {
                        if (hideKeywords.some(k => text.includes(k))) {
                            el.style.setProperty('display', 'none', 'important');
                        }
                    }
                    // Hide A/L buttons at bottom
                    if (r.y > 630 && (text === 'A' || text === 'L') && r.width < 50) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                });
            }
        """)
        await page.wait_for_timeout(500)

        result = await page.screenshot(
            clip={"x": 0, "y": 38, "width": 1100, "height": 662}
        )

        with open("tv_clean5.png", "wb") as f:
            f.write(result)
        import os
        sz = os.path.getsize("tv_clean5.png") / 1024
        print(f"Size: {sz:.1f}KB")

        # Verify
        from PIL import Image
        import numpy as np
        img = Image.open("tv_clean5.png").convert("RGB")
        arr = np.array(img)
        chart = arr[5:625, 5:1025]
        red = np.sum((chart[:,:,0] > 200) & (chart[:,:,1] < 80) & (chart[:,:,2] < 80))
        total = chart.shape[0] * chart.shape[1]
        print(f"Red candles: {red/total*100:.2f}%")

        await browser.close()

asyncio.run(test())
