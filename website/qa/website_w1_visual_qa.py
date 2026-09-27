"""Browser-based W1 visual and interaction checks for the Website foundation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:3010/"
SCREENSHOT_ROOT = ROOT / "qa" / "screenshots" / "w1"
RESULT_PATH = ROOT / "qa" / "w1_visual_results.json"
VIEWPORTS = {
    "desktop-1440x900": (1440, 900),
    "desktop-1280x800": (1280, 800),
    "tablet-1024x768": (1024, 768),
    "tablet-768x1024": (768, 1024),
    "mobile-390x844": (390, 844),
    "mobile-375x812": (375, 812),
}


def main() -> int:
    """Capture screenshots and return a non-zero result for any failed check."""
    results: list[dict[str, object]] = []

    def check(
        viewport: str,
        theme: str,
        name: str,
        passed: bool,
        detail: str = "",
    ) -> None:
        results.append({
            "viewport": viewport,
            "theme": theme,
            "check": name,
            "passed": passed,
            "detail": detail,
        })

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for viewport_name, (width, height) in VIEWPORTS.items():
            is_mobile_nav = width < 1024
            for theme in ("dark", "light"):
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    reduced_motion="reduce",
                )
                context.add_init_script(
                    f"window.localStorage.setItem('website-theme', '{theme}');"
                )
                page = context.new_page()
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(500)

                screenshot_dir = SCREENSHOT_ROOT / theme
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = screenshot_dir / f"{viewport_name}.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
                check(viewport_name, theme, "screenshot captured", screenshot_path.exists(), str(screenshot_path))

                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                check(viewport_name, theme, "no horizontal overflow", not overflow)
                check(viewport_name, theme, "header visible", page.locator("header.website-header").is_visible())
                check(viewport_name, theme, "footer visible", page.locator("footer.website-footer").is_visible())
                check(viewport_name, theme, "main landmark visible", page.locator("main#main-content").is_visible())
                check(viewport_name, theme, "skip link exists", page.locator("a.skip-link").count() == 1)
                check(viewport_name, theme, "three feature cards", page.locator(".feature-card__title").count() == 3)
                check(viewport_name, theme, "three stats items", page.locator(".stats-strip__item").count() == 3)
                check(viewport_name, theme, "two form controls", page.locator(".form-field__control").count() == 2)

                actual_theme = page.locator("html").get_attribute("data-theme")
                check(viewport_name, theme, "theme applied", actual_theme == theme, str(actual_theme))
                reduced_motion = page.evaluate("window.matchMedia('(prefers-reduced-motion: reduce)').matches")
                check(viewport_name, theme, "reduced motion media state", reduced_motion)

                button_labels = page.locator("button").evaluate_all(
                    "els => els.map(el => ({text: el.textContent?.trim(), label: el.getAttribute('aria-label')}))"
                )
                labelled = all(item["text"] or item["label"] for item in button_labels)
                check(viewport_name, theme, "buttons have accessible names", labelled)

                page.keyboard.press("Tab")
                focus_style = page.evaluate(
                    "getComputedStyle(document.activeElement).outlineStyle"
                )
                check(viewport_name, theme, "keyboard focus is visible", focus_style != "none", focus_style)

                if is_mobile_nav:
                    toggle = page.locator(".website-header__mobile-toggle")
                    check(viewport_name, theme, "mobile menu toggle visible", toggle.is_visible())
                    toggle.click()
                    menu_open = page.locator("#website-mobile-menu").get_attribute("data-open") == "true"
                    check(viewport_name, theme, "mobile menu opens", menu_open)
                    page.keyboard.press("Escape")
                    menu_closed = page.locator("#website-mobile-menu").get_attribute("data-open") != "true"
                    check(viewport_name, theme, "Escape closes mobile menu", menu_closed)
                else:
                    check(viewport_name, theme, "desktop navigation visible", page.locator(".website-header__nav").is_visible())
                    check(viewport_name, theme, "mobile toggle hidden", not page.locator(".website-header__mobile-toggle").is_visible())

                before_theme = page.locator("html").get_attribute("data-theme")
                page.locator(".theme-toggle").click()
                after_theme = page.locator("html").get_attribute("data-theme")
                check(viewport_name, theme, "theme toggle changes theme", before_theme != after_theme)
                context.close()
        browser.close()

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    print(f"W1 visual checks: {passed} PASS, {failed} FAIL")
    print(f"Results: {RESULT_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
