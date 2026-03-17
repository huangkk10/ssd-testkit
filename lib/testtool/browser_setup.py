"""
browser_setup — Playwright browser environment helpers.

Provides utilities for ensuring the Playwright Chromium browser binary is
installed on the current machine.  Intended for use by any testtool that
drives a web UI via Playwright (e.g. PHM, future tools).

Usage::

    from lib.testtool.browser_setup import ensure_playwright_chromium

    ensure_playwright_chromium(logger)   # call once in precondition step

**PyInstaller / reboot safety note**
-------------------------------------
When running inside a PyInstaller bundle, each process launch extracts to a
*new* ``_MEIxxxxxx`` temp directory.  If Playwright uses its default browser
path (relative to that temp dir) the Chromium binary installed in run-1 is
invisible to run-2 after a reboot.

To avoid this we pin ``PLAYWRIGHT_BROWSERS_PATH`` to a *persistent* directory
under ``%LOCALAPPDATA%`` at module import time.  Setting it here (before any
Playwright import) ensures the env var is already in place when Playwright
resolves browser paths, both for the ``launch()`` check and for the
``node cli.js install chromium`` subprocess.

**Bundled browser support**
-------------------------------------
When ``ensure_playwright_chromium()`` is called, it first checks for a bundled
Chromium directory at ``<cwd>/bin/playwright-browsers/``.  If found, it
overrides ``PLAYWRIGHT_BROWSERS_PATH`` to point there — enabling fully offline
operation on target PCs without network access.

Priority order:
  1. ``<cwd>/bin/playwright-browsers/``  (shipped inside the release package)
  2. ``%LOCALAPPDATA%\\playwright-browsers``  (persistent per-machine cache)
  3. Online download via ``node cli.js install chromium``  (requires network)

To prepare the bundled browser before packaging::

    playwright install chromium
    xcopy /E /I %LOCALAPPDATA%\\playwright-browsers bin\\playwright-browsers
"""

import os
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Persistent browser cache — survives PyInstaller temp-dir rotation & reboots
# ---------------------------------------------------------------------------
_PERSISTENT_BROWSERS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "playwright-browsers",
)
# setdefault: only set if the caller hasn't already overridden it
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _PERSISTENT_BROWSERS_DIR)

# Relative path (from cwd) where a bundled Chromium may be pre-placed.
_BUNDLED_BROWSERS_RELPATH = "bin/playwright-browsers"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_playwright_chromium(logger=None, force: bool = False) -> bool:
    """
    Ensure the Playwright Chromium browser binary is present on this machine.

    The ``playwright`` Python package and its Node.js driver
    (``node.exe`` + ``cli.js``) are bundled inside ``RunTest.exe`` via
    PyInstaller datas so they are always available in a packaged environment.
    However, the Chromium browser binary (~300 MB) cannot be bundled and must
    be either pre-placed or downloaded once per machine.

    This function:

    1. Checks for a bundled browser at ``<cwd>/bin/playwright-browsers/``.
       If found, ``PLAYWRIGHT_BROWSERS_PATH`` is overridden to point there,
       enabling fully offline operation on target PCs.
    2. If ``force=True``, removes any existing ``chromium-*`` directories
       inside the resolved path so that a clean reinstall is performed.
    3. Tries to launch Chromium headlessly to detect whether it is already
       installed (skipped when ``force=True``).
    4. If missing (or forced), invokes the *bundled* ``node.exe cli.js install
       chromium`` — this works correctly even on machines that have never had
       Python or Playwright installed because it uses the driver shipped with
       the package, not ``sys.executable``.

    Args:
        logger: Optional Python logger.  Pass any ``logging.Logger`` instance
                (or the result of ``get_module_logger()``) to get log output.
                If ``None``, messages are silently discarded.
        force:  When ``True``, remove any existing Chromium installation first
                and always run a fresh install.  Useful for verifying that the
                bundled browser or online download works correctly.

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

    # ── Step 0: resolve browser path (bundled takes priority) ────────────
    bundled_dir = Path(_BUNDLED_BROWSERS_RELPATH)
    using_bundled = bundled_dir.exists()
    if using_bundled:
        browsers_dir = str(bundled_dir.resolve())
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_dir
        _log_info(f"[browser_setup] Bundled Playwright browsers found — using: {browsers_dir}")
    else:
        browsers_dir = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", _PERSISTENT_BROWSERS_DIR)
        _log_info(f"[browser_setup] PLAYWRIGHT_BROWSERS_PATH={browsers_dir}")

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

    # ── Step 1 (force only, non-bundled only): remove existing Chromium ──
    # Bundled browsers are pre-installed offline assets — never delete them.
    # Only force-reinstall when using the persistent per-machine cache path.
    if force and not using_bundled:
        browsers_path_obj = Path(browsers_dir)
        removed = []
        if browsers_path_obj.exists():
            for entry in browsers_path_obj.iterdir():
                if entry.is_dir() and entry.name.startswith("chromium-"):
                    import shutil as _shutil
                    _shutil.rmtree(entry)
                    removed.append(entry.name)
        if removed:
            _log_info(f"[browser_setup] Removed existing Chromium: {', '.join(removed)}")
        else:
            _log_info("[browser_setup] No existing Chromium found — proceeding with fresh install")

    # ── Step 2: quick launch check (skipped when force=True on non-bundled) ─
    if not (force and not using_bundled):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            _log_info("[browser_setup] Playwright Chromium browser is ready")
            return True
        except Exception:
            pass  # Binary missing — fall through to install

    # ── Step 3: install via bundled node.exe + cli.js ─────────────────────
    # compute_driver_executable() resolves paths relative to playwright's
    # own __file__, so it works in both frozen (RunTest.exe) and dev environments.
    # The PLAYWRIGHT_BROWSERS_PATH env var is inherited by the subprocess so
    # the binary lands in the correct directory.
    _log_info(
        f"[browser_setup] Installing Playwright Chromium to {browsers_dir} ..."
    )
    try:
        node_exe, cli_js = compute_driver_executable()
        result = subprocess.run(
            [node_exe, cli_js, "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300,
            env=os.environ,   # explicitly forward — includes PLAYWRIGHT_BROWSERS_PATH
        )
        if result.returncode == 0:
            _log_info(f"[browser_setup] Playwright Chromium installed successfully → {browsers_dir}")
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
