"""Intercept widget embed page, inject custom CSS/JS for colors + hide header."""
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

INJECT = """
<script>
// Wait for widget, then customize
(function() {
    var check = setInterval(function() {
        var cw = window.chartWidget;
        if (cw && cw._paneWidgets && cw._paneWidgets[0]) {
            clearInterval(check);
            try {
                var pane = cw._paneWidgets[0];
                var model = pane._model;
                if (model && model.mainSeries) {
                    model.mainSeries._setProperties({
                        upColor: '#2962ff',
                        downColor: '#1a1a1a',
                        borderUpColor: '#2962ff',
                        borderDownColor: '#1a1a1a',
                        wickUpColor: '#2962ff',
                        wickDownColor: '#1a1a1a'
                    });
                    if (model.fullUpdate) model.fullUpdate();
                }
            } catch(e) { console.log('color err:', e); }
        }
    }, 500);
})();
</script>
<style>
/* Hide ALL non-chart UI elements */
[class*="header"], [class*="toolbar"], [class*="control"],
[class*="title"], [class*="tabs"], [class*="button"],
[class*="legend"], [class*="symbol"], [class*="info"],
[class*="group"], [class*="widgetbar"], [class*="status"],
.chart-page .header, .chart-page .toolbar,
.layout__area--top, .layout__area--left,
.layout__area--right, .layout__area--bottom,
div[class*="Header"], div[class*="Toolbar"],
div[class*="ControlBar"]
{ display: none !important; }
.chart-page, .chart-markup-table, .chart-container
{ top: 0 !important; margin-top: 0 !important; }
body { overflow: hidden !important; background: #fff; }
</style>
"""

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        page.on("pageerror", lambda e: print(f"ERR: {e}"))
        page.on("console", lambda msg: print(f"LOG: {msg.text}"))

        # Intercept the HTML response and inject customization
        async def handle(route):
            resp = await route.fetch()
            body = await resp.text()
            # Inject our custom JS/CSS before </head>
            if "</head>" in body:
                body = body.replace("</head>", INJECT + "</head>")
            await route.fulfill(body=body, content_type="text/html")

        await page.route("**/widgetembed/**", handle)
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(8000)

        await page.screenshot(path="tv_route_final.png")
        import os
        sz = os.path.getsize("tv_route_final.png") / 1024
        print(f"Size: {sz:.1f}KB")
        await browser.close()

asyncio.run(test())
