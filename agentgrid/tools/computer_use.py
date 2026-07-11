"""Playwright execution arm for the Computer Use browser environment.

Implements the action vocabulary documented in COMPUTER_USE.md (browser
environment table) against a real Playwright page. This module only
executes actions — it has no model-calling logic; see
`agentgrid/llm/computer_use.py` for the request/response loop that
decides *which* actions to run.

Sandboxing: a `BrowserSession` will only ever navigate to URLs starting
with the `allowed_prefix` it was constructed with (Google's own safety
guidance calls for an allowlist — this is ours, scoped to the run's own
git worktree).
"""

from __future__ import annotations

import time

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800


class ComputerUseError(Exception):
    pass


def _denorm(value: int | None, span: int) -> int | None:
    return None if value is None else int(value / 1000 * span)


class BrowserSession:
    def __init__(self, allowed_prefix: str) -> None:
        from playwright.sync_api import sync_playwright  # type: ignore
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._context = self._browser.new_context(
            viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT})
        self.page = self._context.new_page()
        self.allowed_prefix = allowed_prefix

    def _guard(self, url: str) -> None:
        if url and not url.startswith(self.allowed_prefix):
            raise ComputerUseError(
                f"blocked navigation outside sandbox: {url!r} "
                f"(allowed prefix: {self.allowed_prefix!r})")

    def goto(self, url: str) -> None:
        self._guard(url)
        self.page.goto(url)
        self.page.wait_for_timeout(200)

    def screenshot(self) -> bytes:
        return self.page.screenshot(type="png")

    def execute(self, name: str, args: dict) -> dict:
        """Run one browser-environment Computer Use action.

        Never raises for ordinary UI misses (unhandled action, bad
        selector, etc.) — those go back to the model as an error result
        so it can adapt, exactly like a real UI interaction would fail
        gracefully. Only sandbox violations raise.
        """
        ax = _denorm(args.get("x"), SCREEN_WIDTH)
        ay = _denorm(args.get("y"), SCREEN_HEIGHT)
        try:
            if name == "click":
                self.page.mouse.click(ax, ay)
            elif name == "double_click":
                self.page.mouse.dblclick(ax, ay)
            elif name == "triple_click":
                self.page.mouse.click(ax, ay, click_count=3)
            elif name == "middle_click":
                self.page.mouse.click(ax, ay, button="middle")
            elif name == "right_click":
                self.page.mouse.click(ax, ay, button="right")
            elif name == "mouse_down":
                self.page.mouse.move(ax, ay)
                self.page.mouse.down()
            elif name == "mouse_up":
                self.page.mouse.up()
            elif name == "move":
                self.page.mouse.move(ax, ay)
            elif name == "type":
                if ax is not None and ay is not None:
                    self.page.mouse.click(ax, ay)
                self.page.keyboard.type(args.get("text", ""))
                if args.get("press_enter"):
                    self.page.keyboard.press("Enter")
            elif name == "drag_and_drop":
                sx = _denorm(args["start_x"], SCREEN_WIDTH)
                sy = _denorm(args["start_y"], SCREEN_HEIGHT)
                ex = _denorm(args["end_x"], SCREEN_WIDTH)
                ey = _denorm(args["end_y"], SCREEN_HEIGHT)
                self.page.mouse.move(sx, sy)
                self.page.mouse.down()
                self.page.mouse.move(ex, ey)
                self.page.mouse.up()
            elif name == "wait":
                time.sleep(min(float(args.get("seconds", 1)), 3))
            elif name == "press_key":
                self.page.keyboard.press(args["key"])
            elif name == "key_down":
                self.page.keyboard.down(args["key"])
            elif name == "key_up":
                self.page.keyboard.up(args["key"])
            elif name == "hotkey":
                self.page.keyboard.press("+".join(args.get("keys", [])))
            elif name == "take_screenshot":
                pass  # a fresh screenshot is captured after every action anyway
            elif name == "scroll":
                mag = int(args.get("magnitude_in_pixels", 300))
                direction = args.get("direction", "down")
                dx = mag if direction == "right" else -mag if direction == "left" else 0
                dy = mag if direction == "down" else -mag if direction == "up" else 0
                self.page.mouse.move(ax or SCREEN_WIDTH // 2, ay or SCREEN_HEIGHT // 2)
                self.page.mouse.wheel(dx, dy)
            elif name == "go_back":
                self.page.go_back()
            elif name == "go_forward":
                self.page.go_forward()
            elif name == "navigate":
                self._guard(args.get("url", ""))
                self.page.goto(args["url"])
            else:
                return {"error": f"unhandled action: {name}"}
            self.page.wait_for_timeout(200)
            return {"ok": True, "url": self.page.url}
        except ComputerUseError:
            raise
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def close(self) -> None:
        try:
            self._browser.close()
            self._pw.stop()
        except Exception:
            pass
