"""Page rendering for the visual verifier — Functionality #8.

With playwright installed: real chromium screenshot of the page.
Without it: graceful degradation — the verifier receives the raw HTML
source instead and judges structure/colors from markup. The pipeline
never blocks on this dependency.
"""

from __future__ import annotations

from pathlib import Path


def take_screenshot(html_path: Path, out_png: Path) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return False, ("playwright not installed — visual verification falls back "
                       "to HTML source inspection (pip install playwright && "
                       "playwright install chromium for real screenshots)")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1024, "height": 768})
            page.goto(f"file://{Path(html_path).resolve()}")
            page.wait_for_timeout(250)
            out_png.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out_png), full_page=True)
            browser.close()
        return True, f"screenshot saved: {out_png}"
    except Exception as exc:
        return False, f"screenshot failed ({type(exc).__name__}: {exc}) — falling back to HTML source"
