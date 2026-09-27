"""Explore widget internals to find the volume series."""
import asyncio, json
from urllib.parse import quote
from playwright.async_api import async_playwright

OVERRIDES = json.dumps({
    "mainSeriesProperties.candleStyle.upColor": "#2962ff",
    "mainSeriesProperties.candleStyle.downColor": "#1a1a1a",
})

URL = (
    "https://s.tradingview.com/widgetembed/"
    "?symbol=OANDA:XAUUSD&interval=5"
    "&hidesidetoolbar=1&theme=light&style=1"
    "&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true"
    f"&overrides={quote(OVERRIDES)}"
)

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(8000)

        info = await page.evaluate("""
            () => {
                const cw = window.chartWidget;
                const results = {};
                if (!cw) return {error: 'no chartWidget'};

                // Explore top-level
                results.topKeys = Object.getOwnPropertyNames(cw).slice(0, 40);

                // paneWidgets
                if (cw._paneWidgets) {
                    results.paneWidgetsType = Array.isArray(cw._paneWidgets) ? 'array' : typeof cw._paneWidgets;
                    if (Array.isArray(cw._paneWidgets)) {
                        results.paneCount = cw._paneWidgets.length;
                        const pane = cw._paneWidgets[0];
                        if (pane) {
                            results.paneKeys = Object.getOwnPropertyNames(pane).slice(0, 30);
                            // Look for sources
                            if (pane._sources) {
                                results.sources = pane._sources.map(s => ({
                                    type: s._type || s.type || 'unknown',
                                    keys: Object.getOwnPropertyNames(s).slice(0, 10)
                                }));
                            }
                            if (pane._chartModel) {
                                const cm = pane._chartModel;
                                results.chartModelKeys = Object.getOwnPropertyNames(cm).slice(0, 40);
                                if (cm.mainSeries) {
                                    results.mainSeriesKeys = Object.getOwnPropertyNames(cm.mainSeries).slice(0, 30);
                                    results.mainSeriesType = cm.mainSeries._type;
                                }
                            }
                        }
                    }
                }

                // Try the "chart" getter
                try {
                    results.chartFn = typeof cw.chart;
                } catch(e) {}

                // Check for panes() function
                if (typeof cw.panes === 'function') {
                    results.hasPanesFn = true;
                    try {
                        const panes = cw.panes();
                        results.panesCount = panes.length;
                        if (panes[0]) {
                            results.pane0Keys = Object.getOwnPropertyNames(panes[0]).slice(0, 30);
                        }
                    } catch(e) { results.panesErr = e.message; }
                }

                return results;
            }
        """)

        import json as j
        print(j.dumps(info, indent=2, default=str)[:4000])
        await browser.close()

asyncio.run(test())
