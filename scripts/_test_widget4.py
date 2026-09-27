"""Test widget color customization — try series API."""
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
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # Try multiple API patterns to change candle colors
        result = await page.evaluate("""
            () => {
                const w = window;
                const results = [];

                // Method 1: chartWidget API
                if (w.chartWidget) {
                    try {
                        const c = w.chartWidget.chart();
                        if (c) {
                            results.push('chartWidget.chart() found');
                            // Try getAllSeries
                            try {
                                const studies = c.getAllStudies();
                                results.push('studies: ' + studies.length);
                            } catch(e) { results.push('getAllStudies: ' + e.message); }
                        }
                    } catch(e) { results.push('chartWidget: ' + e.message); }
                }

                // Method 2: Look for TradingView widget instance
                try {
                    const iframe = document.querySelector('iframe');
                    if (iframe) {
                        results.push('iframe found: ' + iframe.src.substring(0, 50));
                    }
                } catch(e) {}

                // Method 3: List available properties on chartWidget
                if (w.chartWidget) {
                    const props = Object.getOwnPropertyNames(w.chartWidget);
                    results.push('chartWidget props: ' + props.join(', ').substring(0, 200));
                }

                return results;
            }
            """)

        print("Results:")
        for r in result:
            print(f"  {r}")

        # Try hiding elements with CSS
        await page.add_style_tag(content="""
            .header-1dv5l8h5, .header-1lxtn36v, .tabs-1h9k2w4r,
            [class*="header"], [class*="toolbar"], [class*="title"],
            .group-w0p2z8f9, .button-1b7y1w5h { display: none !important; }
            .chart-container { top: 0 !important; }
        """)
        await page.wait_for_timeout(1000)

        # Take screenshot of just the chart canvas
        canvas = await page.query_selector("canvas")
        if canvas:
            box = await canvas.bounding_box()
            print(f"Canvas: {box['width']}x{box['height']} @ ({box['x']},{box['y']})")

        await page.screenshot(path="tv_final.png")
        print("Saved tv_final.png")
        await browser.close()

asyncio.run(test())
