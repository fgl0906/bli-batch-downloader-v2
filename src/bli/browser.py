"""Playwright 瀏覽器生命週期（優先本機 Chrome）。"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from src.config import ACTION_TIMEOUT_MS


class BrowserSession:
    def __init__(self, download_dir: Path) -> None:
        self.download_dir = download_dir
        self._pw: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self) -> Page:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        try:
            self.browser = self._pw.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--start-maximized"],
            )
        except Exception:
            self.browser = self._pw.chromium.launch(
                headless=False,
                args=["--start-maximized"],
            )
        self.context = self.browser.new_context(
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        self.context.set_default_timeout(ACTION_TIMEOUT_MS)
        self.page = self.context.new_page()
        return self.page

    def close(self) -> None:
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
        finally:
            if self._pw:
                self._pw.stop()
            self.page = None
            self.context = None
            self.browser = None
            self._pw = None
