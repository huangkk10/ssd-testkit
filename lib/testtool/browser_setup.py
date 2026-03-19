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
Chromium directory at ``<app_dir>/bin/playwright-browsers/`` where
``<app_dir>`` is resolved via ``path_manager.app_dir`` in packaged executables
(safe at import time, ignores process cwd) or via ``Path(__file__).parents[2]``
in development.  If found, ``PLAYWRIGHT_BROWSERS_PATH`` is overridden there —
enabling fully offline operation on target PCs without network access.

This resolution also runs at **module import time**, so post-reboot recovery
runs where ``test_01_precondition`` is skipped still have the correct browser
path in place before ``test_05`` calls ``open_browser()``.

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

# Sub-path (relative to the app/project root) where a bundled Chromium lives.
_BUNDLED_BROWSERS_RELPATH = "bin/playwright-browsers"


def _resolve_bundled_dir() -> Path:
    """
    Return the absolute path to the bundled browser directory.

    In a PyInstaller-packaged exe ``path_manager.app_dir`` is the flat exe
    directory regardless of the *process* cwd, so it is safe to call at any
    time — including at module import time before the fixture has called
    ``os.chdir()``.

    In a development environment the project root is inferred from this
    file's location (``lib/testtool/browser_setup.py`` → 2 parents up).
    """
    try:
        from path_manager import path_manager as _pm  # type: ignore[import]
        base = Path(_pm.app_dir)
    except ImportError:
        # Development environment — project root is 2 dirs above this file.
        base = Path(__file__).resolve().parents[2]
    return base / _BUNDLED_BROWSERS_RELPATH


# ---------------------------------------------------------------------------
# Module-level: resolve PLAYWRIGHT_BROWSERS_PATH immediately on import.
#
# This must happen at import time (not only inside ensure_playwright_chromium)
# so that the correct path is in effect for EVERY process launch — including
# post-reboot recovery runs where test_01_precondition (which calls
# ensure_playwright_chromium) is skipped because it already completed.
#
# Using _resolve_bundled_dir() (absolute path via path_manager) rather than
# a cwd-relative Path() avoids the pitfall where the auto-start BAT on
# Windows launches the exe with an unpredictable cwd.
#
# Priority:
#   1. <app_dir>/bin/playwright-browsers/  — bundled, offline-capable
#   2. %LOCALAPPDATA%/playwright-browsers  — persistent per-machine cache
# ---------------------------------------------------------------------------
_bundled_at_import = _resolve_bundled_dir()
if _bundled_at_import.exists():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_bundled_at_import)
else:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _PERSISTENT_BROWSERS_DIR)

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
    2. If ``force=True`` **and** the bundled path is NOT in use, removes any
       ``chromium-*`` directories in the persistent cache so a clean reinstall
       from the internet is performed.  The bundled dir is purposely left
       intact: deleting it on an offline target PC would leave nothing to fall
       back to.
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
        force:  When ``True``, perform a clean reinstall.  For the persistent
                LOCALAPPDATA cache this means deleting and re-downloading.
                For the bundled ``bin/playwright-browsers/`` path this is a
                no-op (the existing browser is kept and verified in-place).

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
    # Priority:
    #   1. <project_root>/bin/playwright-browsers  (via path_manager / __file__)
    #   2. <cwd>/bin/playwright-browsers           (cwd may have been changed to
    #      the test case dir by _setup_working_directory before this call)
    #   3. %LOCALAPPDATA%/playwright-browsers      (persistent per-machine cache)
    bundled_dir = _resolve_bundled_dir()
    using_bundled = bundled_dir.exists()
    if not using_bundled:
        cwd_bundled = Path.cwd() / _BUNDLED_BROWSERS_RELPATH
        if cwd_bundled.exists():
            bundled_dir = cwd_bundled
            using_bundled = True
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

    # ── Step 1 (force only): remove existing Chromium dirs ──────────────
    # Bundled dirs are skipped: deleting them would leave the tool with no
    # way to recover on a network-isolated target PC.  Only the persistent
    # LOCALAPPDATA cache can be rebuilt from the internet.
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

    # ── Step 2: quick launch check ────────────────────────────────────────
    # For non-bundled paths with force=True this is skipped (we want a clean
    # reinstall from the internet).  For the bundled path — even when
    # force=True — we verify in-place since the browser cannot be re-downloaded
    # offline; if the launch succeeds we're done.
    if not force or using_bundled:
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
