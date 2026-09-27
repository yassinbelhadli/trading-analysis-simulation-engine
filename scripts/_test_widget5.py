"""Final widget test — hide header, try color override via internal API."""
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
        "&save_image=0"
        "&enable_publishing=0"
        "&show_popup_button=0"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 800})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # Hide ALL header/toolbar elements via CSS
        await page.add_style_tag(content="""
            .header-1dv5l8h5, .header-1lxtn36v,
            [class*="header"],
            [class*="toolbar"],
            [class*="title-"],
            .group-,
            .button-,
            [class*="control-bar"],
            [class*="chart-toolbar"],
            .chart-page .header,
            .chart-markup-table .header
            { display: none !important; }
            .chart-container { margin-top: 0 !important; }
            .chart-markup-table { top: 0 !important; }
        """)
        await page.wait_for_timeout(500)

        # Try to modify candle colors via internal API
        try:
            await page.evaluate("""
                () => {
                    const cw = window.chartWidget;
                    if (!cw) return;
                    // Access pane widgets
                    const panes = cw._paneWidgets;
                    if (panes && panes[0]) {
                        const pane = panes[0];
                        // Try to get the chart model
                        const model = pane._model;
                        if (model) {
                            // Try to access series
                            const series = model.mainSeries;
                            if (series) {
                                // Set overrides via internal methods
                                series._setProperties({
                                    upColor: '#2962ff',
                                    downColor: '#1a1a1a',
                                    borderUpColor: '#2962ff',
                                    borderDownColor: '#1a1a1a',
                                    wickUpColor: '#2962ff',
                                    wickDownColor: '#1a1a1a'
                                });
                                model.fullUpdate();
                                model.dispatchEvent('seriesChanged');
                            }
                        }
                    }
                }
            """)
            print("Internal color override attempted")
        except Exception as e:
            print(f"Internal override error: {e}")

        # Wait for chart to re-render
        await page.wait_for_timeout(2000)

        # Try to screenshot ONLY the chart (crop to canvas area)
        canvas = await page.query_selector("canvas")
        if canvas:
            box = await canvas.bounding_box()
            print(f"Canvas: {box['width']}x{box['height']} @ ({box['x']},{box['y']})")
            await canvas.screenshot(path="tv_clean_chart.png")
            print("Cropped chart saved")

        await page.wait_for_timeout(500)
        await page.screenshot(path="tv_final_clean.png")
        print("Full page saved")

        await browser.close()

asyncio.run(test())
