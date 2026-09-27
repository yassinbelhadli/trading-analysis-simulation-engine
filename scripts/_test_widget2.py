"""Test widget customization via JS injection."""
import asyncio
from playwright.async_api import async_playwright

async def test():
    url = (
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

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 800})

        # Intercept and inject before page loads
        await page.route("**/chart/**", lambda route: route.continue_())
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Try to override candle colors via JS
        try:
            result = await page.evaluate("""
                () => {
                    // Try various widget API access patterns
                    const w = window;
                    const keys = Object.keys(w).filter(k => k.includes('widget') || k.includes('tv') || k.includes('chart'));
                    return keys;
                }
            """)
            print(f"Widget-related window keys: {result[:20]}")
        except Exception as e:
            print(f"JS error: {e}")

        # Try to inject CSS overrides for red→black
        await page.add_style_tag(content="""
            /* Force candle colors */
            /* This won't work inside canvas, but let's try */
        """)

        # Look at what's available in the page context
        try:
            html = await page.content()
            # Find script tags with chart initialization
            print(f"Page title: {await page.title()}")
            print(f"URL: {page.url}")
        except:
            pass

        await page.screenshot(path="tv_widget.png")
        print("Screenshot saved")

        await browser.close()

asyncio.run(test())
