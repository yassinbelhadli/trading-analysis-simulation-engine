"""Find the TradingView logo element."""
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

        elems = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('body *').forEach(el => {
                    const cls = (el.className || '').toString();
                    const tag = el.tagName;
                    // Look for logo, watermark, attribution elements
                    if (/logo|watermark|attribution|brand|trademark/i.test(cls)
                        || (tag === 'A' && (el.href || '').includes('tradingview'))
                        || (tag === 'IMG')) {
                        const r = el.getBoundingClientRect();
                        results.push({
                            tag, cls: cls.substring(0, 70),
                            x: Math.round(r.x), y: Math.round(r.y),
                            w: Math.round(r.width), h: Math.round(r.height),
                            href: (el.href || '').substring(0, 60),
                            text: (el.textContent || '').trim().substring(0, 40),
                            visible: getComputedStyle(el).display !== 'none'
                        });
                    }
                });
                return results;
            }
        """)
        print("Logo candidates:")
        for e in elems:
            print(f"  <{e['tag']}> @ ({e['x']},{e['y']}) {e['w']}x{e['h']} vis={e['visible']}")
            print(f"    cls='{e['cls']}' href='{e['href']}' txt='{e['text']}'")

        await browser.close()

asyncio.run(test())
