"""Full test: serve HTML via HTTP, capture TradingView widget.\
Symbols: OANDA:XAUUSD, CAPITALCOM:US100, COINBASE:BTCUSD"""
import asyncio, threading, os, sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.async_api import async_playwright

HOST = "127.0.0.1"
PORT = 8989
SCRIPTS = Path(__file__).resolve().parent
TEMPLATE = SCRIPTS / "chart_template.html"

def _serve():
    os.chdir(str(SCRIPTS))
    s = HTTPServer((HOST, PORT), SimpleHTTPRequestHandler)
    s.serve_forever()

threading.Thread(target=_serve, daemon=True).start()

async def test():
    for sym, tv_sym in [
        ("Gold", "OANDA:XAUUSD"),
        ("Nasdaq", "CAPITALCOM:US100"),
        ("Bitcoin", "COINBASE:BTCUSD"),
    ]:
        html = TEMPLATE.read_text(encoding="utf-8")
        html = html.replace("__SYMBOL__", tv_sym).replace("__INTERVAL__", "5")
        tmp = SCRIPTS / f"_tmp_{sym.lower()}.html"
        tmp.write_text(html, encoding="utf-8")
        print(f"\n=== {sym} ===")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1100, "height": 700})
            page.on("pageerror", lambda e: print(f"  ERR: {e}"))
            await page.goto(f"http://{HOST}:{PORT}/{tmp.name}", timeout=60000)
            await page.wait_for_timeout(12000)

            canvases = await page.query_selector_all("canvas")
            txt = await page.inner_text("body")
            print(f"  Canvases: {len(canvases)} | Body: {txt[:100]}")

            fp = SCRIPTS / f"_out_{sym.lower()}.png"
            await page.screenshot(path=str(fp))
            sz = fp.stat().st_size / 1024
            print(f"  Size: {sz:.1f}KB")

            await browser.close()

        try:
            tmp.unlink()
        except:
            pass

asyncio.run(test())
