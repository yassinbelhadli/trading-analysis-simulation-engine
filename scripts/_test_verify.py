"""Quick verify — capture a local screenshot of the TV widget."""
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

async def test():
    html_path = Path(__file__).resolve().parent / "chart_template.html"
    html = html_path.read_text(encoding="utf-8")
    html = html.replace("__SYMBOL__", "OANDA:XAUUSD").replace("__INTERVAL__", "5")

    tmp = Path(__file__).resolve().parent / "_tmp_v.html"
    tmp.write_text(html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        await page.goto(f"file:///{tmp.as_posix()}", wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(10000)

        fp = Path(__file__).resolve().parent / "_verify.png"
        await page.screenshot(path=str(fp))
        print(f"Saved to {fp}")
        print(f"Size: {fp.stat().st_size / 1024:.1f}KB")

        # Check for error or blank
        text = await page.inner_text("body")
        print(f"Page text (first 200): {text[:200]}")

        canvas = await page.query_selector("canvas")
        if canvas:
            print("Canvas found!")
            box = await canvas.bounding_box()
            print(f"  Box: {box}")

        # Check for error divs
        err = await page.query_selector("[class*='error'], [class*='Error'], [class*='overlay'], #chart_error")
        if err:
            print(f"ERROR element: {await err.inner_text()}")
        else:
            print("No error elements found")

        await browser.close()

    try:
        tmp.unlink()
    except:
        pass

asyncio.run(test())
