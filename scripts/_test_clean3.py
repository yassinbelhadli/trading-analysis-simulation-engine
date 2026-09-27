"""Precise hiding — target only specific text/button elements."""
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

        # Hide specific elements by text content
        await page.evaluate("""
            () => {
                // Hide elements containing specific keywords (top info bar)
                const hideKeywords = ['Gold Spot', 'U.S. Dollar', 'OANDA', 'Vol', 'Ticks',
                                      'Spread', 'Session', '⋮', 'X'];
                const all = document.querySelectorAll('div, span, button');
                all.forEach(el => {
                    const text = el.textContent.trim();
                    if (hideKeywords.some(k => text.includes(k))) {
                        if (text.length < 100) {  // avoid hiding big containers
                            el.style.display = 'none';
                        }
                    }
                });

                // Hide A/L buttons at bottom (single char buttons)
                all.forEach(el => {
                    const text = el.textContent.trim();
                    if ((text === 'A' || text === 'L') && el.tagName === 'BUTTON') {
                        const r = el.getBoundingClientRect();
                        // Only if at bottom of page
                        if (r.y > 600) {
                            el.style.display = 'none';
                        }
                    }
                });
            }
        """)
        await page.wait_for_timeout(500)

        result = await page.screenshot(
            clip={"x": 0, "y": 38, "width": 1100, "height": 662}
        )

        with open("tv_clean3.png", "wb") as f:
            f.write(result)
        import os
        sz = os.path.getsize("tv_clean3.png") / 1024
        print(f"Size: {sz:.1f}KB")

        await browser.close()

asyncio.run(test())
