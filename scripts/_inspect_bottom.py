"""Inspect bottom area: what's above the time scale + where's the TV logo."""
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

        # Get ALL elements in bottom region with any text/icon info
        elems = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('body *').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.y >= 560 && r.y <= 700) {
                        // Get computed styles to see visibility
                        const style = getComputedStyle(el);
                        const isVisible = style.display !== 'none' && style.visibility !== 'hidden'
                                          && style.opacity !== '0';
                        results.push({
                            tag: el.tagName,
                            x: Math.round(r.x), y: Math.round(r.y),
                            w: Math.round(r.width), h: Math.round(r.height),
                            cls: (el.className || '').toString().substring(0, 60),
                            visible: isVisible,
                            text: (el.textContent || '').trim().substring(0, 40)
                        });
                    }
                });
                results.sort((a, b) => a.y - b.y || a.x - b.x);
                return results;
            }
        """)
        print("Bottom area elements (y 560-700):")
        for e in elems:
            print(f"  <{e['tag']}> @ ({e['x']},{e['y']}) {e['w']}x{e['h']} vis={e['visible']} "
                  f"cls='{e['cls']}' txt='{e['text']}'")

        await browser.close()

asyncio.run(test())
