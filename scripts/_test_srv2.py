"""Debug HTTP server + TV widget constructor approach."""
import asyncio, threading, os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.async_api import async_playwright

HOST = "127.0.0.1"
PORT = 8990
SCRIPTS = Path(__file__).resolve().parent
TEMPLATE = SCRIPTS / "chart_template.html"

def _serve():
    os.chdir(str(SCRIPTS))
    HTTPServer((HOST, PORT), SimpleHTTPRequestHandler).serve_forever()

threading.Thread(target=_serve, daemon=True).start()

async def test():
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__SYMBOL__", "OANDA:XAUUSD").replace("__INTERVAL__", "5")
    tmp = SCRIPTS / "_tmp_debug.html"
    tmp.write_text(html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})

        # Log ALL console messages
        page.on("console", lambda msg: print(f"  [{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"  [PAGE_ERROR] {err}"))
        page.on("load", lambda: print("  [LOAD] page loaded"))
        page.on("domcontentloaded", lambda: print("  [DOM] DOM content loaded"))

        try:
            await page.goto(f"http://{HOST}:{PORT}/{tmp.name}",
                          timeout=60000, wait_until="networkidle")
            print("  [NAV] navigation complete")
        except Exception as e:
            print(f"  [NAV_ERROR] {e}")

        await page.wait_for_timeout(15000)

        txt = await page.inner_text("body")
        print(f"  Body text (100): {txt[:100]}")

        canvases = await page.query_selector_all("canvas")
        print(f"  Canvases: {len(canvases)}")

        await page.screenshot(path="tv_debug.png")
        sz = os.path.getsize("tv_debug.png") / 1024
        print(f"  Size: {sz:.1f}KB")

        await browser.close()

    try:
        tmp.unlink()
    except:
        pass

asyncio.run(test())
