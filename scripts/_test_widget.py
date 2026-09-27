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
        "&studies="
        "&enable_publishing=0"
        "&show_popup_button=0"
        "&save_image=0"
        "&toolbarbg=f1f3f6"
        "&noStudies=true"
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 800})
        await page.goto(url, wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="tv_test2.png", full_page=True)

        # Check for MACD
        body = await page.inner_text("body")
        if "MACD" in body:
            print("MACD found")
        else:
            print("No MACD")

        # List canvases
        canvases = await page.query_selector_all("canvas")
        print(f"Canvases: {len(canvases)}")
        for i, c in enumerate(canvases):
            box = await c.bounding_box()
            if box:
                print(f"  #{i}: {box['width']}x{box['height']} @ ({box['x']},{box['y']})")

        # Try to find the chart title/header elements
        elements = await page.query_selector_all(".chart-container *, .header *, .title *, .tabs *")
        print(f"Chart container children: {len(elements)}")

        await browser.close()

asyncio.run(test())
