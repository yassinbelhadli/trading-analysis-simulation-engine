"""Remove bottom time scale + icons, keep chart + right price scale."""
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
                document.querySelectorAll('div, span, button, svg, canvas').forEach(el => {
                    const r = el.getBoundingClientRect();
                    // Top info bar text (y 38-82, small elements)
                    if (r.y > 38 && r.y < 82 && r.width < 500 && r.height < 80) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                    // Bottom icons / A-L buttons (y 600-660)
                    if (r.y >= 600 && r.y < 660 && r.width < 1050) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                    // Time scale area (y >= 660): hide everything
                    if (r.y >= 660) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                });
            }
        """)
        await page.wait_for_timeout(500)

        result = await page.screenshot(
            clip={"x": 0, "y": 38, "width": 1100, "height": 633}
        )
        with open("tv_noscale.png", "wb") as f:
            f.write(result)
        import os
        sz = os.path.getsize("tv_noscale.png") / 1024
        print(f"Size: {sz:.1f}KB")
        await browser.close()

asyncio.run(test())
