"""Explore all visible HTML elements on the widget page (not canvas)."""
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

        # Get all non-canvas elements with position info
        elems = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('body *:not(script):not(canvas)');
                const results = [];
                all.forEach(el => {
                    const r = el.getBoundingClientRect();
                    const text = (el.textContent || '').trim();
                    if (r.width > 0 && r.height > 0 && text) {
                        results.push({
                            tag: el.tagName,
                            x: Math.round(r.x), y: Math.round(r.y),
                            w: Math.round(r.width), h: Math.round(r.height),
                            text: text.substring(0, 80)
                        });
                    }
                });
                // Sort by y position
                results.sort((a, b) => a.y - b.y);
                return results;
            }
        """)
        print("Visible HTML elements:")
        for e in elems:
            print(f"  <{e['tag']}> @ ({e['x']},{e['y']}) {e['w']}x{e['h']} — '{e['text']}'")

        await browser.close()

asyncio.run(test())
