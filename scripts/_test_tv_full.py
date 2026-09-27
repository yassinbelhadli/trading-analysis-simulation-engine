"""Test TV widget constructor via local HTTP server."""
import asyncio, threading, io
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.async_api import async_playwright

HOST = "127.0.0.1"
PORT = 8976
SCRIPTS_DIR = Path(__file__).resolve().parent


def _start_server():
    os.chdir(SCRIPTS_DIR)
    server = HTTPServer((HOST, PORT), SimpleHTTPRequestHandler)
    server.serve_forever()


import os
t = threading.Thread(target=_start_server, daemon=True)
t.start()


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        page.on("console", lambda msg: print(f"LOG: {msg.text}"))
        page.on("pageerror", lambda err: print(f"ERR: {err}"))

        await page.goto(f"http://{HOST}:{PORT}/chart_template.html", timeout=60000)
        await page.wait_for_timeout(15000)

        # Check if widget loaded
        txt = await page.inner_text("body")
        print(f"Body: {txt[:200]}")

        canvases = await page.query_selector_all("canvas")
        print(f"Canvas count: {len(canvases)}")

        await page.screenshot(path="tv_constructor.png")
        sz = os.path.getsize("tv_constructor.png") / 1024
        print(f"Size: {sz:.1f}KB")
        await browser.close()


asyncio.run(test())
