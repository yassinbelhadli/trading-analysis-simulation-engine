"""Test direct widget URL + CSS/JS injection for color + header."""
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
        page = await browser.new_page(viewport={"width": 1200, "height": 800})
        page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))

        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)

        # Check page content
        txt = await page.inner_text("body")
        print(f"Body text: {txt[:150]}")

        canvases = await page.query_selector_all("canvas")
        print(f"Canvases: {len(canvases)}")

        # Hide header via CSS
        await page.add_style_tag(content="""
            [class*="header"], [class*="Header"],
            [class*="toolbar"], [class*="Toolbar"],
            [class*="control"], [class*="Control"],
            [class*="title"], [class*="Title"],
            [class*="tabs"], [class*="Tabs"],
            [class*="button"], [class*="Button"]
            { display: none !important; }
            .chart-page { top: 0 !important; }
            body { overflow: hidden !important; }
        """)
        await page.wait_for_timeout(1000)

        await page.screenshot(path="tv_injected.png")
        import os
        sz = os.path.getsize("tv_injected.png") / 1024
        print(f"Size: {sz:.1f}KB")
        await browser.close()

asyncio.run(test())
