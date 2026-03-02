"""
PHM (Powerhouse Mountain) UI Monitor

Web UI automation for PHM using Playwright.

PHM is a Node.js application that serves a web interface on
``http://localhost:<port>`` (default 1337).  This module drives the
browser-based UI via Playwright instead of a native Win32 automation tool.

Architecture (confirmed 2026-03-02):
    PowerhouseMountain.exe  â†’  Node.js backend (localhost:1337)
                            â†’  Browser opens http://localhost:1337

.. note::
    CSS selectors / locators below marked ``# TODO`` must be verified
    after launching PHM and inspecting elements with browser DevTools or
    ``playwright codegen http://localhost:1337``.

Usage::

    from lib.testtool.phm.ui_monitor import PHMUIMonitor

    monitor = PHMUIMonitor(host='localhost', port=1337)
    monitor.wait_for_ready(timeout=30)
    monitor.open_browser(headless=False)
    monitor.navigate_to_collector()
    monitor.set_cycle_count(10)
    monitor.set_test_duration(60)
    monitor.set_modern_standby_mode(True)
    monitor.start_test()
    monitor.wait_for_completion(timeout=3600)
    monitor.take_screenshot('./testlog/result.png')
    monitor.close_browser()
"""

import time
import os
import socket
from typing import Optional
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    Page = None
    Browser = None
    BrowserContext = None
    PlaywrightTimeoutError = Exception
    _PLAYWRIGHT_AVAILABLE = False

from .exceptions import PHMUIError, PHMTimeoutError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# CSS Selectors / Locators â€” UPDATE after inspecting real PHM Web UI
# ---------------------------------------------------------------------------
# Use browser DevTools (F12) or:
#   playwright codegen http://localhost:1337
# to find the real selectors.

_SEL_COLLECTOR_TAB    = 'a[href*="collector"], button:has-text("Collector")'  # TODO
_SEL_START_BTN        = 'button:has-text("Start")'                            # TODO
_SEL_STOP_BTN         = 'button:has-text("Stop")'                             # TODO
_SEL_STATUS_LABEL     = '[data-testid="status"], .status-label'               # TODO
_SEL_CYCLE_INPUT      = 'input[name="cycleCount"], input[placeholder*="cycle"]'  # TODO
_SEL_DURATION_INPUT   = 'input[name="duration"], input[placeholder*="min"]'   # TODO
_SEL_MODERN_STANDBY   = 'input[type="checkbox"][name*="standby"], label:has-text("Modern Standby") input'  # TODO

# Text values that indicate the test has finished
_COMPLETION_STATUSES = {'pass', 'fail', 'completed', 'done', 'error'}


class PHMUIMonitor:
    """
    Web UI monitor for PHM (Powerhouse Mountain).

    Controls PHM via Playwright by driving the web interface at
    ``http://<host>:<port>``.

    Example::

        monitor = PHMUIMonitor(host='localhost', port=1337)
        monitor.wait_for_ready(timeout=30)
        monitor.open_browser(headless=False)
        monitor.navigate_to_collector()
        monitor.set_cycle_count(10)
        monitor.start_test()
        monitor.wait_for_completion(timeout=3600)
        monitor.close_browser()
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 1337,
        headless: bool = False,
        browser_timeout: int = 30000,
    ):
        """
        Initialize PHM UI monitor.

        Args:
            host: PHM web server host (default ``'localhost'``).
            port: PHM web server port (default ``1337``).
            headless: Run browser in headless mode (default ``False``).
            browser_timeout: Playwright default timeout in milliseconds.

        Raises:
            PHMUIError: If playwright is not installed.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            raise PHMUIError(
                "playwright is required for UI monitoring. "
                "Install it with: pip install playwright && playwright install chromium"
            )

        self.host = host
        self.port = port
        self.headless = headless
        self.browser_timeout = browser_timeout
        self.base_url = f"http://{host}:{port}"

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._connected = False

    # ------------------------------------------------------------------
    # Server readiness
    # ------------------------------------------------------------------

    def wait_for_ready(self, timeout: int = 30) -> bool:
        """
        Poll until the PHM web server is accepting TCP connections.

        Args:
            timeout: Total seconds to wait.

        Returns:
            True when the server is ready.

        Raises:
            PHMTimeoutError: If not ready within *timeout* seconds.
        """
        deadline = time.time() + timeout
        logger.info(f"Waiting for PHM server at {self.base_url} ...")
        while time.time() < deadline:
            try:
                with socket.create_connection((self.host, self.port), timeout=1):
                    logger.info("PHM server is ready")
                    return True
            except OSError:
                time.sleep(1)

        raise PHMTimeoutError(
            f"PHM server {self.base_url} did not become ready within {timeout}s"
        )

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def open_browser(self, headless: Optional[bool] = None) -> None:
        """
        Launch a Playwright Chromium browser and open the PHM web UI.

        Args:
            headless: Override instance headless setting for this call.

        Raises:
            PHMUIError: If browser launch or page load fails.
        """
        if headless is None:
            headless = self.headless

        logger.info(f"Opening Playwright browser (headless={headless})")
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=headless)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.browser_timeout)
            self._page.goto(self.base_url)
            self._page.wait_for_load_state('networkidle')
            self._connected = True
            logger.info(f"Browser opened at {self.base_url}")
        except Exception as exc:
            raise PHMUIError(f"Failed to open browser: {exc}") from exc

    def close_browser(self) -> None:
        """Close the browser and stop Playwright."""
        logger.info("Closing Playwright browser")
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._connected = False

    def _require_connected(self) -> None:
        """Raise PHMUIError if browser is not open."""
        if not self._connected or self._page is None:
            raise PHMUIError(
                "Browser not connected. Call open_browser() first."
            )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_collector(self) -> None:
        """
        Click the Collector tab in the PHM navigation.

        Raises:
            PHMUIError: If the Collector tab is not found.
        """
        self._require_connected()
        logger.info("Navigating to Collector tab")
        try:
            self._page.click(_SEL_COLLECTOR_TAB)
            self._page.wait_for_load_state('networkidle')
        except PlaywrightTimeoutError as exc:
            raise PHMUIError(
                f"Collector tab not found (selector: {_SEL_COLLECTOR_TAB!r}). "
                "Update _SEL_COLLECTOR_TAB with the real selector."
            ) from exc
        except Exception as exc:
            raise PHMUIError(f"Failed to navigate to Collector: {exc}") from exc

    # ------------------------------------------------------------------
    # Parameter configuration
    # ------------------------------------------------------------------

    def set_cycle_count(self, count: int) -> None:
        """
        Set the number of test cycles in the PHM web UI.

        Args:
            count: Positive integer cycle count.

        Raises:
            PHMUIError: If the cycle count input is not found.
        """
        self._require_connected()
        logger.info(f"Setting cycle count to {count}")
        try:
            self._page.fill(_SEL_CYCLE_INPUT, str(count))
        except Exception as exc:
            raise PHMUIError(
                f"Failed to set cycle count (selector: {_SEL_CYCLE_INPUT!r}): {exc}"
            ) from exc

    def set_test_duration(self, minutes: int) -> None:
        """
        Set the test duration in the PHM web UI.

        Args:
            minutes: Test duration in minutes.

        Raises:
            PHMUIError: If the duration input is not found.
        """
        self._require_connected()
        logger.info(f"Setting test duration to {minutes} minutes")
        try:
            self._page.fill(_SEL_DURATION_INPUT, str(minutes))
        except Exception as exc:
            raise PHMUIError(
                f"Failed to set duration (selector: {_SEL_DURATION_INPUT!r}): {exc}"
            ) from exc

    def set_modern_standby_mode(self, enabled: bool) -> None:
        """
        Enable or disable the Modern Standby (S0ix) checkbox.

        Args:
            enabled: True to enable, False to disable.

        Raises:
            PHMUIError: If the checkbox is not found.
        """
        self._require_connected()
        logger.info(f"Setting Modern Standby mode: {enabled}")
        try:
            checkbox = self._page.locator(_SEL_MODERN_STANDBY)
            is_checked = checkbox.is_checked()
            if is_checked != enabled:
                checkbox.click()
        except Exception as exc:
            raise PHMUIError(
                f"Failed to set Modern Standby (selector: {_SEL_MODERN_STANDBY!r}): {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Test control
    # ------------------------------------------------------------------

    def start_test(self) -> None:
        """
        Click the Start button to begin the PHM test.

        Raises:
            PHMUIError: If the Start button is not found.
        """
        self._require_connected()
        logger.info("Clicking Start button")
        try:
            self._page.click(_SEL_START_BTN)
        except Exception as exc:
            raise PHMUIError(
                f"Failed to click Start button (selector: {_SEL_START_BTN!r}): {exc}"
            ) from exc

    def stop_test(self) -> None:
        """
        Click the Stop button to halt the running test.

        Raises:
            PHMUIError: If the Stop button is not found.
        """
        self._require_connected()
        logger.info("Clicking Stop button")
        try:
            self._page.click(_SEL_STOP_BTN)
        except Exception as exc:
            raise PHMUIError(
                f"Failed to click Stop button (selector: {_SEL_STOP_BTN!r}): {exc}"
            ) from exc

    def wait_for_completion(self, timeout: int = 3600) -> bool:
        """
        Poll the status label until the test completes or timeout expires.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True when a completion status is detected.

        Raises:
            PHMTimeoutError: If the test has not completed within *timeout*s.
        """
        self._require_connected()
        logger.info(f"Waiting for PHM test completion (timeout={timeout}s)")
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_current_status()
            if status.lower() in _COMPLETION_STATUSES:
                logger.info(f"PHM test completed with status: {status}")
                return True
            time.sleep(5)

        raise PHMTimeoutError(
            f"PHM test did not complete within {timeout} seconds"
        )

    # ------------------------------------------------------------------
    # Status & screenshot
    # ------------------------------------------------------------------

    def get_current_status(self) -> str:
        """
        Read the current status text from the PHM status label.

        Returns:
            Status string as shown in the UI (e.g. ``"Running"``, ``"Pass"``).

        Raises:
            PHMUIError: If the status element is not found.
        """
        self._require_connected()
        try:
            elem = self._page.locator(_SEL_STATUS_LABEL).first
            return elem.inner_text().strip()
        except Exception as exc:
            raise PHMUIError(
                f"Failed to read status (selector: {_SEL_STATUS_LABEL!r}): {exc}"
            ) from exc

    def take_screenshot(self, path: str) -> str:
        """
        Capture the full page as a PNG screenshot.

        Args:
            path: File path to write the PNG image.

        Returns:
            The resolved file path.

        Raises:
            PHMUIError: If screenshot capture fails.
        """
        self._require_connected()
        resolved = str(Path(path).resolve())
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        try:
            self._page.screenshot(path=resolved, full_page=True)
            logger.info(f"Screenshot saved: {resolved}")
            return resolved
        except Exception as exc:
            raise PHMUIError(f"Failed to take screenshot: {exc}") from exc

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """True if the browser is open and connected."""
        return self._connected

    @property
    def page(self):
        """The active Playwright Page, or None if not connected."""
        return self._page

