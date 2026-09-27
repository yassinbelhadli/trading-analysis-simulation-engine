"""Debug: show all canvas positions to understand layout."""
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

        sizes = await page.evaluate("""
            () => {
                const cs = document.querySelectorAll('canvas');
                return Array.from(cs).map((c, i) => {
                    const r = c.getBoundingClientRect();
                    return {i, w: c.width, h: c.height,
                            x: r.x, y: r.y, rw: r.width, rh: r.height};
                });
            }
        """)
        for s in sizes:
            print(f"  Canvas {s['i']}: {s['w']}x{s['h']} "
                  f"@ ({s['x']},{s['y']}) = {s['rw']}x{s['rh']}")

        # Also check for non-canvas elements that take space
        heights = await page.evaluate("""
            () => {
                const els = document.querySelectorAll('body > *');
                return Array.from(els).map(e => ({
                    tag: e.tagName,
                    h: e.offsetHeight,
                    text: (e.textContent || '').trim().substring(0, 50)
                }));
            }
        """)
        for h in heights:
            print(f"  Element <{h['tag']}> h={h['h']}: '{h['text']}'")

        await browser.close()

asyncio.run(test())
