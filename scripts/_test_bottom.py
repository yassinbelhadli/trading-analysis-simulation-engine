"""Analyze the bottom region of the chart to identify the 'indicator'."""
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

        # List all elements near the bottom (y > 600)
        elems = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('body *').forEach(el => {
                    const r = el.getBoundingClientRect();
                    const t = (el.textContent || '').trim();
                    if (r.y > 590 && r.width > 10 && r.height > 3) {
                        results.push({
                            tag: el.tagName,
                            x: Math.round(r.x), y: Math.round(r.y),
                            w: Math.round(r.width), h: Math.round(r.height),
                            text: t.substring(0, 60)
                        });
                    }
                });
                results.sort((a, b) => a.y - b.y);
                return results.slice(0, 40);
            }
        """)
        print("Elements at bottom (y > 590):")
        for e in elems:
            print(f"  <{e['tag']}> @ ({e['x']},{e['y']}) {e['w']}x{e['h']} — '{e['text']}'")

        await browser.close()

asyncio.run(test())
