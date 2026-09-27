"""Test widget candle color customization via chartWidget API."""
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
        await page.wait_for_timeout(4000)

        # Try to customize candle colors via chartWidget API
        try:
            await page.evaluate("""
                () => {
                    const w = window.chartWidget;
                    if (w && w.chart) {
                        const chart = w.chart();
                        chart.applyOverrides({
                            'mainSeriesProperties.candleStyle.upColor': '#2962ff',
                            'mainSeriesProperties.candleStyle.downColor': '#1a1a1a',
                            'mainSeriesProperties.candleStyle.borderUpColor': '#2962ff',
                            'mainSeriesProperties.candleStyle.borderDownColor': '#1a1a1a',
                            'mainSeriesProperties.candleStyle.wickUpColor': '#2962ff',
                            'mainSeriesProperties.candleStyle.wickDownColor': '#1a1a1a',
                        });
                        return 'OK';
                    }
                    return 'no chartWidget';
                }
            """)
            print("Candle colors applied")
        except Exception as e:
            print(f"JS error: {e}")

        await page.wait_for_timeout(1000)
        await page.screenshot(path="tv_widget_blue_black.png")

        # Check pixel colors to verify
        from PIL import Image
        import numpy as np
        img = Image.open("tv_widget_blue_black.png").convert("RGB")
        arr = np.array(img)
        chart_area = arr[50:700, 50:1050]
        blue = np.sum((chart_area[:,:,0] < 60) & (chart_area[:,:,1] > 120) & (chart_area[:,:,2] > 200))
        red = np.sum((chart_area[:,:,0] > 200) & (chart_area[:,:,1] < 80) & (chart_area[:,:,2] < 80))
        black = np.sum(np.all(chart_area < 50, axis=2))
        print(f"Blue pixels: {blue}")
        print(f"Red pixels: {red}")
        print(f"Black pixels: {black}")

        # Also try to hide header elements
        try:
            await page.evaluate("""
                () => {
                    // Hide various UI elements
                    document.querySelectorAll('.header, .tabs, .title, .toolbar, .widgetbar')
                        .forEach(el => el.style.display = 'none');
                    return 'hidden';
                }
            """)
            print("Header elements hidden")
        except:
            pass

        await page.wait_for_timeout(500)
        await page.screenshot(path="tv_widget_clean.png")
        print("Clean screenshot saved")

        await browser.close()

asyncio.run(test())
