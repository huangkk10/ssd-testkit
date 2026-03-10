"""
browser_setup — Playwright browser environment helpers.

Provides utilities for ensuring the Playwright Chromium browser binary is
installed on the current machine.  Intended for use by any testtool that
drives a web UI via Playwright (e.g. PHM, future tools).

Usage::

    from lib.testtool.browser_setup import ensure_playwright_chromium

    ensure_playwright_chromium(logger)   # call once in precondition step
"""

import subprocess
from typing import Optional

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_playwright_chromium(logger=None) -> bool:
    """
    Ensure the Playwright Chromium browser binary is present on this machine.

    The ``playwright`` Python package and its Node.js driver
    (``node.exe`` + ``cli.js``) are bundled inside ``RunTest.exe`` via
    PyInstaller datas so they are always available in a packaged environment.
    However, the Chromium browser binary (~300 MB) cannot be bundled and must
    be downloaded once per machine.

    This function:

    1. Tries to launch Chromium headlessly to detect whether it is already
       installed.
    2. If missing, invokes the *bundled* ``node.exe cli.js install chromium``
       — this works correctly even on machines that have never had Python or
       Playwright installed because it uses the driver shipped with the package,
       not ``sys.executable``.

    Args:
        logger: Optional Python logger.  Pass any ``logging.Logger`` instance
                (or the result of ``get_module_logger()``) to get log output.
                If ``None``, messages are silently discarded.

    Returns:
        ``True``  if Chromium is ready (already present or just installed).
        ``False`` if installation failed or the ``playwright`` package is not
                  importable.
    """
    def _log_info(msg: str) -> None:
        if logger:
            logger.info(msg)

    def _log_warning(msg: str) -> None:
        if logger:
            logger.warning(msg)

    try:
        from playwright.sync_api import sync_playwright
        from playwright._impl._driver import compute_driver_executable
    except ImportError:
        _log_warning(
            "[browser_setup] playwright package is not importable — "
            "any test that uses PHMUIMonitor or other web-UI tools will fail. "
            "Ensure playwright is bundled in RunTest.exe."
        )
        return False

    # ── Step 1: quick launch check ────────────────────────────────────────
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        _log_info("[browser_setup] Playwright Chromium browser is ready")
        return True
    except Exception:
        pass  # Binary missing — fall through to install

    # ── Step 2: install via bundled node.exe + cli.js ─────────────────────
    # compute_driver_executable() resolves paths relative to playwright's
    # own __file__, so it works in both frozen (RunTest.exe) and dev environments.
    _log_info("[browser_setup] Playwright Chromium not found — installing via bundled driver...")
    try:
        node_exe, cli_js = compute_driver_executable()
        result = subprocess.run(
            [node_exe, cli_js, "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            _log_info("[browser_setup] Playwright Chromium installed successfully")
            return True
        else:
            _log_warning(
                f"[browser_setup] Playwright Chromium install failed "
                f"(rc={result.returncode}): {result.stderr.strip()}"
            )
            return False
    except Exception as exc:
        _log_warning(f"[browser_setup] Playwright Chromium install error: {exc}")
        return False
