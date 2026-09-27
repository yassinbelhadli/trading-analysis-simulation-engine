"""Hide header by targeting elements via text content, then crop to canvas."""
import asyncio
from playwright.async_api import async_playwright

URL = (
    "https://s.tradingview.com/widgetembed/"
    "?symbol=OANDA:XAUUSD"
    "&interval=5"
    "&hidesidetoolbar=1"
    "&theme=light"
    "&style=1"
    "&timezone=Etc/UTC"
    "&withfooter=0"
    "&hideideas=1"
    "&noStudies=true"
)

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})

        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # Hide all elements that contain specific text patterns
        await page.evaluate("""
            () => {
                const hideTexts = [
                    '1m', '5m', '30m', '1h', 'Indicators',
                    'Gold Spot', 'U.S. Dollar', 'OANDA',
                    'Vol', 'Ticks', 'Spread', 'Session',
                    '//', 'O:', 'H:', 'L:', 'C:',
                ];
                document.querySelectorAll('*').forEach(el => {
                    const t = el.textContent.trim();
                    if (hideTexts.some(h => t.includes(h))) {
                        if (t.length < 60) {  // only small elements
                            el.style.display = 'none';
                        }
                    }
                });
                // Also hide specific selectors
                document.querySelectorAll('[class*="header"], [class*="toolbar"], [class*="control"]')
                    .forEach(el => el.style.display = 'none');
            }
        """)
        await page.wait_for_timeout(500)

        # Screenshot just the main chart canvas (largest canvas)
        canvases = await page.query_selector_all("canvas")
        print(f"Canvas count: {len(canvases)}")

        if len(canvases) >= 2:
            # Main chart canvas is typically the second one
            box = await canvases[1].bounding_box()
            print(f"Main canvas box: {box}")
            if box and box['width'] > 200:
                # Screenshot a region covering the main chart
                await page.screenshot(path="tv_clean_region.png",
                    clip={"x": box['x'], "y": box['y'],
                          "width": box['width'], "height": box['height']})
                import os
                sz = os.path.getsize("tv_clean_region.png") / 1024
                print(f"Region size: {sz:.1f}KB")
        else:
            await page.screenshot(path="tv_clean_fallback.png")

        # Also take full page
        await page.screenshot(path="tv_clean_full.png")
        import os
        sz = os.path.getsize("tv_clean_full.png") / 1024
        print(f"Full size: {sz:.1f}KB")

        await browser.close()

asyncio.run(test())
