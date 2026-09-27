"""Final: clip header + try color override via pane internals."""
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
        await page.wait_for_timeout(6000)

        # Explore widget internals for color override
        info = await page.evaluate("""
            () => {
                const cw = window.chartWidget;
                if (!cw) return 'no chartWidget';
                const p = cw._paneWidgets;
                if (!p || !p[0]) return 'no panes';
                const pane = p[0];
                const keys = Object.keys(pane).filter(k => k.startsWith('_'));
                // Try various model access paths
                const models = {};
                if (pane._model) models._model = Object.keys(pane._model).filter(k => k.includes('eries') || k.includes('eries'));
                if (pane._chartModel) models._chartModel = Object.keys(pane._chartModel).slice(0,10);
                if (pane.model) models.model = typeof pane.model;
                // Check for mainSeries
                if (pane._model && pane._model.mainSeries) {
                    models.mainSeries = typeof pane._model.mainSeries;
                    const ms = pane._model.mainSeries;
                    const msKeys = Object.getOwnPropertyNames(ms).filter(k => !k.startsWith('_')).slice(0,20);
                    models.mainSeriesKeys = msKeys;
                }
                return {paneKeys: keys.slice(0,30), models};
            }
        """)
        print("Widget internals:")
        import json
        print(json.dumps(info, indent=2, default=str))

        # Try color override via requestAnimationFrame to update canvas
        await page.evaluate("""
            () => {
                const cw = window.chartWidget;
                if (!cw || !cw._paneWidgets || !cw._paneWidgets[0]) return;
                const pane = cw._paneWidgets[0];
                const model = pane._model;
                if (!model || !model.mainSeries) return;
                const ms = model.mainSeries;
                // Try to set properties
                if (ms._setProperties) {
                    ms._setProperties({
                        upColor: '#2962ff',
                        downColor: '#1a1a1a',
                        borderUpColor: '#2962ff',
                        borderDownColor: '#1a1a1a',
                        wickUpColor: '#2962ff',
                        wickDownColor: '#1a1a1a'
                    });
                    // Force redraw
                    if (model.fullUpdate) model.fullUpdate();
                    if (model.dispatchEvent) model.dispatchEvent('seriesChanged');
                }
            }
        """)
        await page.wait_for_timeout(2000)

        # Clip screenshot to chart area (y=40 to end)
        await page.screenshot(
            path="tv_final_chart.png",
            clip={"x": 0, "y": 40, "width": 1100, "height": 660}
        )
        import os
        sz = os.path.getsize("tv_final_chart.png") / 1024
        print(f"\nSize: {sz:.1f}KB")

        # Analyze colors
        from PIL import Image
        import numpy as np
        img = Image.open("tv_final_chart.png").convert("RGB")
        arr = np.array(img)
        chart = arr[5:630, 5:1025]  # main chart area (exclude borders)
        blue = np.sum((chart[:,:,0] < 60) & (chart[:,:,1] > 100) & (chart[:,:,2] > 200))
        green = np.sum((chart[:,:,0] < 60) & (chart[:,:,1] > 150) & (chart[:,:,2] < 100))
        red = np.sum((chart[:,:,0] > 200) & (chart[:,:,1] < 80) & (chart[:,:,2] < 80))
        black = np.sum(np.all(chart < 50, axis=2))
        total = chart.shape[0] * chart.shape[1]
        print(f"Blue: {blue/total*100:.2f}% | Green: {green/total*100:.2f}% | Red: {red/total*100:.2f}% | Black: {black/total*100:.2f}%")

        await browser.close()

asyncio.run(test())
