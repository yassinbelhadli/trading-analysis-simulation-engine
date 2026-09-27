"""Check for TradingView logo/watermark in pixel regions."""
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

        # Screenshot full page
        await page.screenshot(path="tv_fullpage.png")

        # Get all canvas contents in bottom-right area (screenshot each canvas)
        canvases = await page.query_selector_all("canvas")
        for i, c in enumerate(canvases):
            box = await c.bounding_box()
            print(f"Canvas {i}: {box['width']}x{box['height']} @ ({box['x']},{box['y']})")

        # Check for <a> elements with href
        links = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('a').forEach(a => {
                    const r = a.getBoundingClientRect();
                    if (r.width > 5 && r.height > 5) {
                        results.push({
                            x: Math.round(r.x), y: Math.round(r.y),
                            w: Math.round(r.width), h: Math.round(r.height),
                            href: (a.href || '').substring(0, 80),
                            txt: (a.textContent || '').trim().substring(0, 40)
                        });
                    }
                });
                return results;
            }
        """)
        print("\nVisible links:")
        for l in links:
            print(f"  @ ({l['x']},{l['y']}) {l['w']}x{l['h']} href='{l['href']}' txt='{l['txt']}'")

        await browser.close()

asyncio.run(test())
