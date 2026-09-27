"""Remove control bar + keep time scale + remove TV logo corner."""
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

        await page.evaluate("""
            () => {
                document.querySelectorAll('div, span, button, svg, canvas').forEach(el => {
                    const r = el.getBoundingClientRect();
                    const cls = (el.className || '').toString();
                    // 1) Top info bar text (y 38-82, small elements)
                    if (r.y > 38 && r.y < 82 && r.width < 500 && r.height < 80) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                    // 2) Control bar (zoom/scroll buttons above time scale)
                    if (cls.includes('control-bar')) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                    // 3) TradingView logo corner (bottom-right)
                    if (r.x >= 1029 && r.y >= 660) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                });
            }
        """)
        await page.wait_for_timeout(500)

        # Clip includes time scale (y=38 to y=700)
        result = await page.screenshot(
            clip={"x": 0, "y": 38, "width": 1100, "height": 662}
        )
        with open("tv_final_v2.png", "wb") as f:
            f.write(result)
        import os
        sz = os.path.getsize("tv_final_v2.png") / 1024
        print(f"Size: {sz:.1f}KB")

        # Verify
        from PIL import Image
        import numpy as np
        img = Image.open("tv_final_v2.png").convert("RGB")
        arr = np.array(img)

        # Time scale should have text (dark pixels at bottom)
        ts = arr[628:658, 5:1025]
        dark_ts = np.sum(np.all(ts < 100, axis=2))
        print(f"Time scale text present: {dark_ts} dark px")

        # Corner should be clean (no logo)
        corner = arr[628:662, 1025:1100]
        dark_corner = np.sum(np.all(corner < 100, axis=2))
        print(f"Corner dark px: {dark_corner}")

        # Control bar area (y 565-595 in clip = y 603-633 original... wait clip starts at 38)
        # Original control bar at y=610-644 -> clip y = 610-38 = 572-606
        cb = arr[570:606, 400:700]
        dark_cb = np.sum(np.all(cb < 100, axis=2))
        print(f"Control bar area dark px: {dark_cb}")

        # Chart should have candles
        chart = arr[20:550, 5:1025]
        red = np.sum((chart[:,:,0] > 200) & (chart[:,:,1] < 80) & (chart[:,:,2] < 80))
        green = np.sum((chart[:,:,0] < 60) & (chart[:,:,1] > 150) & (chart[:,:,2] < 100))
        print(f"Candles: red={red} green={green}")

        await browser.close()

asyncio.run(test())
