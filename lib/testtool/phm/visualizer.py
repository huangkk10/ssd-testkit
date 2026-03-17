"""
PHM Visualizer — Parameterized Automation Library
==================================================

Automates the PHM Web UI Visualizer tab to extract summary data for
any supported metric (PCIeLPM, PCIeLTR, …) and optionally verify that
specific columns meet minimum-threshold requirements.

Public API
----------
- :class:`VisualizerConfig`   — infrastructure / runner settings
- :class:`VisualizerResult`   — return value of :func:`run_visualizer_check`
- :func:`run_visualizer_check` — single-call end-to-end runner

Example usage
-------------
::

    from lib.testtool.phm.visualizer import (
        VisualizerConfig, run_visualizer_check
    )

    cfg = VisualizerConfig(headless=True)

    # PCIeLPM — Standard NVM, verify L1.2 ≥ 90 %
    result = run_visualizer_check(
        metric_name="PCIeLPM",
        device_filter="Standard NVM Express Controller",
        thresholds={"L1.2": 90.0},
        config=cfg,
    )
    assert result.passed, result.verdicts

    # PCIeLTR — all devices, no threshold check
    result2 = run_visualizer_check(
        metric_name="PCIeLTR",
        config=cfg,
    )
    print(result2.rows)
"""

from __future__ import annotations

import csv
import json
import time
import urllib.request
import urllib.parse as _urlparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
    _PW_OK = True
except ImportError:
    _PW_OK = False

from lib.logger import get_module_logger
logger = get_module_logger(__name__)

# ── Default paths ─────────────────────────────────────────────────────────────
_DEFAULT_TRACES_DIR = Path(r"C:\Program Files\PowerhouseMountain\traces")


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualizerConfig:
    """
    Infrastructure and runner configuration for :func:`run_visualizer_check`.

    All fields have sensible defaults — only override what you need.

    Parameters
    ----------
    host
        PHM web-server hostname (default ``"localhost"``).
    port
        PHM web-server port (default ``1337``).
    api_port
        PHM REST API port used by parserService (default ``1338``).
    headless
        Run Chromium without a visible window (default ``False``).
    traces_base_dir
        Root directory where PHM stores Scenario* trace folders.
    output_dir
        Directory to write CSV / JSON output files.
        Defaults to ``<caller_script_dir>/output`` at runtime.
    pause_between_steps
        Seconds to sleep between browser automation steps; useful for
        visual inspection.  Set to ``0`` to disable.
    save_output
        Write CSV and JSON summary files.  Set to ``False`` to skip.
    canvas_wait_seconds
        Maximum seconds to wait for the Visualizer canvas to render
        before raising an error (default ``90``).
    """

    host:                  str            = "localhost"
    port:                  int            = 1337
    api_port:              int            = 1338
    headless:              bool           = False
    traces_base_dir:       Path           = field(
        default_factory=lambda: _DEFAULT_TRACES_DIR
    )
    output_dir:            Optional[Path] = None   # resolved at runtime
    pause_between_steps:   float          = 1.0
    save_output:           bool           = True
    canvas_wait_seconds:   int            = 90  # seconds; raised from 60


# ═══════════════════════════════════════════════════════════════════════════════
# Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualizerResult:
    """
    Return value of :func:`run_visualizer_check`.

    Attributes
    ----------
    metric_name
        The metric name that was queried (e.g. ``"PCIeLPM"``).
    device_filter
        The device sub-string used to filter child items (or ``None``).
    rows
        List of dicts — the filtered summary rows returned by the API.
        Each dict contains columns such as ``"Component"``, ``"L1.2"``, …
    headers
        Column names in display order (includes ``"_title"`` as first column).
    csv_path
        Path to the saved CSV file, or ``None`` if saving was skipped.
    json_path
        Path to the saved JSON file, or ``None`` if saving was skipped.
    verdicts
        Per-row verdict strings (one per threshold check, per row).
    passed
        ``True`` only if all threshold checks passed (or no thresholds).
    """

    metric_name:   str
    device_filter: Optional[str]
    rows:          list   # list[dict]
    headers:       list   # list[str]
    csv_path:      Optional[Path]
    json_path:     Optional[Path]
    verdicts:      list   # list[str]
    passed:        bool


# ═══════════════════════════════════════════════════════════════════════════════
# Public function
# ═══════════════════════════════════════════════════════════════════════════════

def run_visualizer_check(
    metric_name:     str                        = "PCIeLPM",
    device_filter:   Optional[str]              = "Standard NVM Express Controller",
    thresholds:      Optional[dict[str, float]] = None,
    max_thresholds:  Optional[dict[str, float]] = None,
    config:          Optional[VisualizerConfig] = None,
    api_metric_name: Optional[str]              = None,
) -> VisualizerResult:
    """
    Full end-to-end PHM Visualizer check.

    Opens Chromium, navigates to PHM, switches to the Visualizer tab,
    selects *metric_name* with optional exclusive child selection, calls
    the parserService REST API for summary data, optionally saves output
    files, and verifies column thresholds.

    Parameters
    ----------
    metric_name
        Tree item label to search / check / expand in the Visualizer sidebar.
        Also used as the REST API ``name=`` parameter unless *api_metric_name*
        is provided.
        Examples: ``"PCIeLPM"``, ``"PCIe LTR"``.
    device_filter
        Sub-string to exclusively-select among *metric_name*'s children.
        Also used to filter API rows by ``"Component"`` field.
        Pass ``None`` to keep all children and all result rows.
    thresholds
        ``{column_name: minimum_value}`` pairs — column must be **>=** value.
        Example: ``{"L1.2": 90.0}``.
        Pass ``None`` or ``{}`` to skip minimum checks.
    max_thresholds
        ``{column_name: maximum_value}`` pairs — column must be **<=** value.
        Useful for LTR latency checks where lower is better.
        Example: ``{"Min": 50_000_000}`` (50 ms expressed in ns).
        Non-numeric cell values (e.g. ``"No LTR"``) are silently skipped.
        Pass ``None`` or ``{}`` to skip maximum checks.
    config
        Infrastructure settings.  Defaults to :class:`VisualizerConfig`.
    api_metric_name
        Override the ``name=`` parameter sent to the parserService REST API.
        Use when the tree sidebar label differs from the API name
        (e.g. tree shows ``"PCIe LTR"`` but API expects ``"PCIeLTR"``).  
        Defaults to *metric_name* when ``None``.

    Returns
    -------
    VisualizerResult
        Contains filtered rows, saved-file paths, verdict strings, and
        overall pass flag.

    Raises
    ------
    RuntimeError
        If ``playwright`` is not installed.
    AssertionError
        If any threshold check fails (only when *thresholds* is non-empty).
    FileNotFoundError
        If no Scenario* directories or Contents.cycl are found.
    """
    if not _PW_OK:
        raise RuntimeError(
            "playwright is not installed — "
            "run: pip install playwright && playwright install chromium"
        )

    cfg = config if config is not None else VisualizerConfig()
    if thresholds is None:
        thresholds = {}
    if max_thresholds is None:
        max_thresholds = {}
    effective_api_name = api_metric_name if api_metric_name is not None else metric_name

    session = _VisualizerSession(
        cfg, metric_name, device_filter,
        thresholds, max_thresholds, effective_api_name,
    )
    return session.run()


# ═══════════════════════════════════════════════════════════════════════════════
# Internal session class (all browser automation lives here)
# ═══════════════════════════════════════════════════════════════════════════════

class _VisualizerSession:
    """
    Stateful session object that owns the Playwright browser and executes
    the numbered automation steps.  Not meant to be used directly.
    """

    def __init__(
        self,
        cfg:             VisualizerConfig,
        metric_name:     str,
        device_filter:   Optional[str],
        thresholds:      dict[str, float],
        max_thresholds:  dict[str, float],
        api_metric_name: str,
    ) -> None:
        self._cfg             = cfg
        self._metric_name     = metric_name
        self._api_metric_name = api_metric_name
        self._device_filter   = device_filter
        self._thresholds      = thresholds
        self._max_thresholds  = max_thresholds

        # Resolve output directory
        if cfg.output_dir is not None:
            self._output_dir = Path(cfg.output_dir)
        else:
            # Default: same directory as this file plus /output
            self._output_dir = Path(__file__).parent / "output"

    # ── Utilities ────────────────────────────────────────────────────────────

    def _step(self, n: int | str, description: str) -> None:
        logger.info("=" * 60)
        logger.info("  Step %s: %s", n, description)
        logger.info("=" * 60)
        if self._cfg.pause_between_steps > 0:
            time.sleep(self._cfg.pause_between_steps)

    def _dump_debug(self, page, label: str) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        html_path = self._output_dir / f"debug_{label}.html"
        png_path  = self._output_dir / f"debug_{label}.png"
        html_path.write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(png_path), full_page=True)
        logger.debug("HTML dump  → %s", html_path)
        logger.debug("Screenshot → %s", png_path)

    # ── Filesystem helpers ───────────────────────────────────────────────────

    def _find_latest_scenario_dir(self) -> Path:
        base = self._cfg.traces_base_dir
        scenarios = sorted(
            [d for d in base.iterdir() if d.is_dir() and d.name.startswith("Scenario")],
            key=lambda d: d.name,
        )
        if not scenarios:
            raise FileNotFoundError(f"No Scenario* folders found under {base}")
        latest = scenarios[-1]
        logger.info("Latest scenario : %s", latest)
        logger.info("All scenarios (%d) — last 5:", len(scenarios))
        for s in scenarios[-5:]:
            logger.info("    %s", s.name)
        return latest

    def _find_contents_cycl(self, scenario_dir: Path) -> Path:
        direct = scenario_dir / "Contents.cycl"
        if direct.exists():
            logger.info("Contents.cycl (direct): %s", direct)
            return direct
        found = list(scenario_dir.rglob("Contents.cycl"))
        if not found:
            raise FileNotFoundError(
                f"Contents.cycl not found anywhere under {scenario_dir}"
            )
        if len(found) > 1:
            logger.warning("Multiple Contents.cycl — using first:")
            for f in found:
                logger.warning("    %s", f)
        logger.info("Contents.cycl (recursive): %s", found[0])
        return found[0]

    def _find_content_phm(self, scenario_dir: Path) -> Path:
        for cycle_dir in sorted(scenario_dir.glob("Cycle*/Content.phm")):
            return cycle_dir
        raise FileNotFoundError(
            f"Content.phm not found under {scenario_dir}"
        )

    def _build_viewtrace_url(self, contents_cycl: Path) -> str:
        return (
            f"http://{self._cfg.host}:{self._cfg.port}/viewtrace/"
            f"?pathname=opentrace&traceDir={contents_cycl}"
        )

    # ── Browser tree helpers ─────────────────────────────────────────────────

    def _tree_item_info(self, page, text: str) -> dict | None:
        """Return ``{checked, expanded, label}`` for the tree row matching *text*."""
        return page.evaluate(
            """(text) => {
                for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                    const lbl = row.querySelector('button.tree-label');
                    if (!lbl) continue;
                    const nb = lbl.querySelector('span.ng-binding');
                    if (!nb || !nb.innerText.includes(text)) continue;
                    return {
                        checked:  !!lbl.querySelector('span.glyphicon-check'),
                        expanded: !!row.querySelector('i.glyphicon-triangle-bottom'),
                        label:    nb.innerText.trim().slice(0, 80),
                    };
                }
                return null;
            }""",
            text,
        )

    def _tree_check(self, page, text: str) -> str | None:
        """Ensure tree row *text* is checked; only clicks if currently unchecked."""
        return page.evaluate(
            """(text) => {
                for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                    const lbl = row.querySelector('button.tree-label');
                    if (!lbl) continue;
                    const nb = lbl.querySelector('span.ng-binding');
                    if (!nb || !nb.innerText.includes(text)) continue;
                    if (!lbl.querySelector('span.glyphicon-check')) {
                        lbl.click();
                        return 'clicked (was unchecked)';
                    }
                    return 'skipped (already checked)';
                }
                return null;
            }""",
            text,
        )

    def _tree_expand(self, page, text: str) -> str | None:
        """Expand tree row *text*; skips if already expanded."""
        return page.evaluate(
            """(text) => {
                for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                    const lbl = row.querySelector('button.tree-label');
                    if (!lbl) continue;
                    const nb = lbl.querySelector('span.ng-binding');
                    if (!nb || !nb.innerText.includes(text)) continue;
                    if (row.querySelector('i.glyphicon-triangle-bottom'))
                        return 'skipped (already expanded)';
                    const btn = row.querySelector('button.tree-icon');
                    if (btn) { btn.click(); return 'expanded'; }
                    return 'no expand button';
                }
                return null;
            }""",
            text,
        )

    def _tree_set_exclusive(self, page, parent_text: str, keep_text: str) -> list:
        """
        Among the direct children of *parent_text*, ensure only the child
        containing *keep_text* is checked; uncheck all others.
        Returns list of action strings for logging.
        """
        return page.evaluate(
            """([parentText, keepText]) => {
                const rows = [...document.querySelectorAll('tr.tree-grid-row')];
                let parentIdx = -1;
                for (let i = 0; i < rows.length; i++) {
                    const lbl = rows[i].querySelector('button.tree-label');
                    if (!lbl) continue;
                    const nb = lbl.querySelector('span.ng-binding');
                    if (nb && nb.innerText.trim() === parentText) {
                        parentIdx = i;
                        break;
                    }
                }
                if (parentIdx === -1)
                    return ['ERROR: parent not found: ' + parentText];

                const results = [];
                for (let i = parentIdx + 1; i < rows.length; i++) {
                    const row = rows[i];
                    if (row.querySelector('button.tree-icon')) break;
                    const lbl = row.querySelector('button.tree-label');
                    if (!lbl) continue;
                    const nb = lbl.querySelector('span.ng-binding');
                    if (!nb) continue;
                    const text    = nb.innerText.trim();
                    const checked = !!lbl.querySelector('span.glyphicon-check');
                    if (text.includes(keepText)) {
                        if (!checked) { lbl.click(); results.push('checked: '   + text.slice(0, 70)); }
                        else          {              results.push('kept:    '   + text.slice(0, 70)); }
                    } else {
                        if (checked)  { lbl.click(); results.push('unchecked: ' + text.slice(0, 70)); }
                    }
                }
                return results.length ? results : ['no children found or no changes needed'];
            }""",
            [parent_text, keep_text],
        )

    def _tree_uncheck_all(self, page) -> list:
        """Uncheck every checked tree item (clean-slate reset). Returns unchecked labels."""
        return page.evaluate("""() => {
            const unchecked = [];
            for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                const lbl = row.querySelector('button.tree-label');
                if (!lbl) continue;
                if (lbl.querySelector('span.glyphicon-check')) {
                    const nb = lbl.querySelector('span.ng-binding');
                    unchecked.push(nb ? nb.innerText.trim().slice(0, 70) : '?');
                    lbl.click();
                }
            }
            return unchecked;
        }""")

    # ── Save helpers ─────────────────────────────────────────────────────────

    def _save_summary(self, rows: list[dict], headers: list[str]) -> tuple[Path, Path]:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_metric = self._metric_name.replace(" ", "_")
        csv_path  = self._output_dir / f"{safe_metric}_summary_{ts}.csv"
        json_path = self._output_dir / f"{safe_metric}_summary_{ts}.json"

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

        logger.info("CSV  saved → %s", csv_path)
        logger.info("JSON saved → %s", json_path)
        return csv_path, json_path

    # ── Threshold verification ───────────────────────────────────────────────

    def _verify_thresholds(self, rows: list[dict]) -> tuple[list[str], bool]:
        """
        Check lower-bound (self._thresholds, column >= min) and
        upper-bound (self._max_thresholds, column <= max) against all rows.
        Non-numeric cell values are SKIPPED for upper-bound checks (treated
        as "no measurement", e.g. "No LTR").
        Returns (verdict_lines, overall_passed).
        """
        if not self._thresholds and not self._max_thresholds:
            return [], True

        verdicts: list[str] = []
        passed = True

        for row in rows:
            comp = row.get("Component", row.get("_title", "?"))

            # ── lower-bound checks (column >= min_val) ────────────────────
            for col, min_val in self._thresholds.items():
                raw = row.get(col)
                if raw is None:
                    passed = False
                    verdicts.append(f"  ✗ Column '{col}' not found in row: {comp}")
                    continue
                try:
                    val = float(raw)
                except (ValueError, TypeError):
                    passed = False
                    verdicts.append(
                        f"  ✗ Column '{col}' = '{raw}' is not numeric  [{comp}]"
                    )
                    continue
                if val >= min_val:
                    verdicts.append(
                        f"  ✓ PASS  {col} = {val:.4g} ≥ {min_val}  [{comp}]"
                    )
                else:
                    passed = False
                    verdicts.append(
                        f"  ✗ FAIL  {col} = {val:.4g} < {min_val}  [{comp}]"
                    )

            # ── upper-bound checks (column <= max_val) ────────────────────
            for col, max_val in self._max_thresholds.items():
                raw = row.get(col)
                if raw is None:
                    passed = False
                    verdicts.append(f"  ✗ Column '{col}' not found in row: {comp}")
                    continue
                try:
                    val = float(raw)
                except (ValueError, TypeError):
                    # Non-numeric (e.g. "No LTR") — skip, not a failure
                    verdicts.append(
                        f"  — SKIP  {col} = '{raw}' (non-numeric, skipped)  [{comp}]"
                    )
                    continue
                if val <= max_val:
                    verdicts.append(
                        f"  ✓ PASS  {col} = {val:.4g} ns ≤ {max_val:.4g} ns"
                        f" ({max_val/1_000_000:.0f} ms)  [{comp}]"
                    )
                else:
                    passed = False
                    verdicts.append(
                        f"  ✗ FAIL  {col} = {val:.4g} ns > {max_val:.4g} ns"
                        f" ({max_val/1_000_000:.0f} ms)  [{comp}]"
                    )

        return verdicts, passed

    # ── Main run ─────────────────────────────────────────────────────────────

    def run(self) -> VisualizerResult:
        cfg = self._cfg

        # ── Step 0: locate trace files ────────────────────────────────────
        self._step(0, "Locate latest Scenario folder and Contents.cycl")
        latest_scenario = self._find_latest_scenario_dir()
        contents_cycl   = self._find_contents_cycl(latest_scenario)
        logger.info("Contents.cycl : %s", contents_cycl)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=cfg.headless)
            context = browser.new_context(viewport={"width": 1600, "height": 900})
            page    = context.new_page()

            csv_path: Optional[Path]  = None
            json_path: Optional[Path] = None

            try:
                # ── Step 1: navigate to PHM ───────────────────────────────
                self._step(1, f"Open PHM UI at http://{cfg.host}:{cfg.port}")
                page.goto(
                    f"http://{cfg.host}:{cfg.port}",
                    wait_until="networkidle",
                    timeout=30_000,
                )
                logger.info("PHM UI loaded")

                open_trace_btn = page.locator(
                    'button:has-text("Open Trace"), '
                    'a:has-text("Open Trace"), '
                    '[data-testid="open-trace"]'
                ).first

                try:
                    with page.expect_file_chooser(timeout=5_000) as fc_info:
                        open_trace_btn.click(timeout=10_000)
                    fc_info.value.set_files(str(contents_cycl))
                    logger.info("File chooser handled")
                    page.wait_for_url("**/viewtrace/**", timeout=15_000)
                except PWTimeoutError:
                    logger.info("No file-chooser — navigating directly")
                    viewtrace_url = self._build_viewtrace_url(contents_cycl)
                    logger.info("→ %s", viewtrace_url)
                    page.goto(viewtrace_url, wait_until="networkidle", timeout=30_000)

                logger.info("Viewtrace loaded: %s", page.url)
                page.wait_for_timeout(3_000)
                self._dump_debug(page, "after_viewtrace_load")

                # ── Step 2: click Content.phm ─────────────────────────────
                self._step(2, "Click the Content.phm link in CycleSummary")

                phm_link = (
                    page.locator("a").filter(has_text="Content.phm").first
                    if page.locator("a").filter(has_text="Content.phm").count() > 0
                    else page.locator(
                        "[class*='green'], [style*='color: green'], [style*='color:green']"
                    ).filter(has_text=".phm").first
                    if page.locator(
                        "[class*='green'], [style*='color: green'], [style*='color:green']"
                    ).filter(has_text=".phm").count() > 0
                    else page.get_by_text("Content.phm", exact=False).first
                )

                phm_link.wait_for(state="visible", timeout=15_000)
                phm_text = phm_link.inner_text().strip()
                logger.debug("Link text: %s", phm_text)
                phm_link.click()
                logger.info("Content.phm clicked")
                page.wait_for_load_state("networkidle", timeout=30_000)
                # Give PHM backend extra time to parse the trace into Angular
                # scopes before interacting with the Visualizer tab.  In
                # packaged/fast runs 2 s was insufficient; 5 s gives PHM's
                # async parser more breathing room.
                page.wait_for_timeout(5_000)

                # ── Step 3: switch to Visualizer tab ──────────────────────
                self._step(3, "Switch to the Visualizer tab")
                # Use a native Playwright click (not page.evaluate) so that
                # Angular's ng-click handler is triggered via a real browser
                # event.  A synthetic JS .click() from evaluate() can silently
                # no-op if Angular hasn't finished initialising the view yet.
                _vis_selector = 'button[title="Visualize metrics in a timeline"]'
                try:
                    page.locator(_vis_selector).first.wait_for(
                        state="visible", timeout=10_000
                    )
                    page.locator(_vis_selector).first.click()
                    logger.info("Visualizer tab: Visualize metrics in a timeline (native click)")
                except PWTimeoutError:
                    # Fallback: try matching by inner text
                    page.locator('button:has-text("Visualizer")').first.click(timeout=10_000)
                    logger.info("Visualizer tab: Visualizer (text-match fallback)")

                # Wait until the tree rows are actually present in the DOM —
                # this confirms the Visualizer view has finished loading, not
                # just that the tab button was clicked.
                try:
                    page.wait_for_selector(
                        "tr.tree-grid-row", state="visible", timeout=15_000
                    )
                    logger.info("Visualizer tree rows visible — tab loaded successfully")
                except PWTimeoutError:
                    logger.warning(
                        "Tree rows not visible after 15 s — Visualizer tab may not have "
                        "switched.  Proceeding anyway."
                    )
                page.wait_for_timeout(1_000)
                self._dump_debug(page, "after_visualizer_tab")

                # ── Step 4: check metric + expand ─────────────────────────
                self._step(4, f"Check '{self._metric_name}' and expand its children")

                # Clean slate — uncheck everything
                unchecked_all = self._tree_uncheck_all(page)
                logger.info("Unchecked %d item(s):", len(unchecked_all))
                for u in unchecked_all:
                    logger.info("    - %s", u)
                page.wait_for_timeout(600)

                info = self._tree_item_info(page, self._metric_name)
                logger.debug("'%s' state before: %s", self._metric_name, info)

                result = self._tree_check(page, self._metric_name)
                logger.debug("check result: %s", result)

                result = self._tree_expand(page, self._metric_name)
                logger.debug("expand result: %s", result)
                page.wait_for_timeout(2_000)

                # ── Step 5: exclusive-select child (if device_filter set) ──
                if self._device_filter:
                    self._step(5, f"Exclusive-select '{self._device_filter}' under '{self._metric_name}'")
                    actions = self._tree_set_exclusive(
                        page, self._metric_name, self._device_filter
                    )
                    logger.info("Exclusive-select actions (%d):", len(actions))
                    for a in actions:
                        logger.info("    %s", a)
                    page.wait_for_timeout(1_500)

                    nvm_info = self._tree_item_info(page, self._device_filter)
                    logger.debug("Child final state: %s", nvm_info)
                    if nvm_info and not nvm_info["checked"]:
                        logger.warning("Child still unchecked — force-checking…")
                        self._tree_check(page, self._device_filter)

                    # ── Force Angular digest cycle via $rootScope.$apply() ────
                    # page.evaluate() JS .click() may not reliably trigger Angular
                    # Zone.js change detection (especially in packaged/fast runs).
                    # Calling $rootScope.$apply() directly is the canonical way to
                    # force Angular 1.x to process all pending scope changes and
                    # re-render the chart canvas.
                    # As a secondary measure, also fire a bubbling dispatchEvent on
                    # the kept button so the Angular ng-click handler sees a real event.
                    logger.info("Forcing Angular digest cycle via $rootScope.$apply()…")
                    _apply_result = page.evaluate(
                        """(keepText) => {
                            // 1. dispatchEvent on the kept button to satisfy ng-click
                            try {
                                for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                                    const nb = row.querySelector('span.ng-binding');
                                    if (!nb || !nb.innerText.includes(keepText)) continue;
                                    const lbl = row.querySelector('button.tree-label');
                                    if (lbl) {
                                        const evt = new MouseEvent('click',
                                            {bubbles: true, cancelable: true, view: window});
                                        lbl.dispatchEvent(evt);
                                    }
                                    break;
                                }
                            } catch(e) { /* ignore */ }
                            // 2. force Angular $rootScope.$apply()
                            try {
                                const inj = angular.element(document.body).injector();
                                inj.get('$rootScope').$apply();
                                return '$apply ok';
                            } catch(e) {
                                return '$apply error: ' + e.message;
                            }
                        }""",
                        self._device_filter,
                    )
                    logger.info("Angular digest result: %s", _apply_result)
                    page.wait_for_timeout(3_000)
                else:
                    self._step(5, "No device_filter set — all children kept as-is")

                    # ── Force Angular digest cycle via $rootScope.$apply() ────
                    logger.info("Forcing Angular digest cycle via $rootScope.$apply() (no device_filter)…")
                    _apply_result = page.evaluate(
                        """(metricText) => {
                            try {
                                const inj = angular.element(document.body).injector();
                                inj.get('$rootScope').$apply();
                                return '$apply ok';
                            } catch(e) {
                                return '$apply error: ' + e.message;
                            }
                        }""",
                        self._metric_name,
                    )
                    logger.info("Angular digest result: %s", _apply_result)
                    page.wait_for_timeout(3_000)

                # ── Wait for canvas / SVG chart to render ──────────────────
                # Give Angular time to process tree-item clicks before polling.
                page.wait_for_timeout(3_000)
                logger.info("Waiting for canvas to render…")

                # Selector covers both canvas-based and SVG-based PHM charts.
                _CHART_SELECTOR = (
                    "canvas#pageCanvas0, "
                    "canvas, "
                    "svg[class*='chart'], "
                    "[class*='visualizer'] svg, "
                    "[class*='chart-container'] svg"
                )
                canvas_ready = False
                try:
                    page.wait_for_selector(
                        _CHART_SELECTOR,
                        state="visible",
                        timeout=self._cfg.canvas_wait_seconds * 1_000,
                    )
                    # Scroll into view now that the element exists.
                    page.evaluate("""
                        (sel) => {
                            const c = document.querySelector(sel);
                            if (c) c.scrollIntoView({block:'center', inline:'center'});
                        }""", _CHART_SELECTOR)
                    page.wait_for_timeout(500)
                    # Verify it has non-zero dimensions (canvas) or is in the DOM (SVG).
                    _bb = page.evaluate("""
                        (sel) => {
                            const c = document.querySelector(sel);
                            if (!c) return null;
                            const r = c.getBoundingClientRect();
                            return {x: r.x, y: r.y, width: r.width, height: r.height,
                                    tag: c.tagName.toLowerCase()};
                        }""", _CHART_SELECTOR)
                    if _bb and (_bb["width"] > 0 or _bb["tag"] == "svg"):
                        logger.info("Chart element ready: %s", _bb)
                        canvas_ready = True
                    else:
                        logger.warning("Chart element found but zero-size: %s", _bb)
                except PWTimeoutError:
                    logger.warning(
                        "wait_for_selector timed out after %ds — falling back to poll loop",
                        self._cfg.canvas_wait_seconds,
                    )

                # Fallback: manual poll for canvas width > 0.
                if not canvas_ready:
                    for _i in range(self._cfg.canvas_wait_seconds * 2):
                        _bb = page.evaluate("""() => {
                            const c = document.querySelector('canvas#pageCanvas0, canvas');
                            if (!c) return null;
                            const r = c.getBoundingClientRect();
                            return {x: r.x, y: r.y, width: r.width, height: r.height};
                        }""")
                        if _bb and _bb["width"] > 0:
                            logger.info("Canvas ready after %.1fs (fallback poll): %s", _i * 0.5, _bb)
                            canvas_ready = True
                            break
                        page.wait_for_timeout(500)

                if not canvas_ready:
                    self._dump_debug(page, "canvas_wait_timeout")
                    raise AssertionError(
                        f"Canvas did not render within {cfg.canvas_wait_seconds}s."
                    )

                # ── Step 6: call parserService REST API ───────────────────
                self._step(6, f"REST API → getSummaryData for '{self._metric_name}'")
                phm_file = self._find_content_phm(latest_scenario)
                logger.info("PHM file: %s", phm_file)

                encoded_path = _urlparse.quote(str(phm_file), safe="")
                api_url = (
                    f"http://localhost:{cfg.api_port}/parserService"
                    f"?target=getSummaryData"
                    f"&url={encoded_path}"
                    f"&name={_urlparse.quote(self._api_metric_name)}"
                    f"&minTime=0"
                    f"&maxTime=1844674407370950000"
                )
                logger.debug("API URL: %s…", api_url[:140])

                # --- Retry loop: parserService may still be indexing the
                # trace when the canvas first renders.  Allow up to
                # _API_MAX_RETRIES attempts with _API_RETRY_DELAY_S seconds
                # between each attempt before giving up.
                _API_MAX_RETRIES   = 5
                _API_RETRY_DELAY_S = 5

                _raw    = None
                report  = {}
                api_exc = None
                for _attempt in range(1, _API_MAX_RETRIES + 1):
                    try:
                        with urllib.request.urlopen(api_url, timeout=15) as _resp:
                            _raw = _resp.read().decode("utf-8")
                        api_exc = None
                    except Exception as _e:
                        api_exc = _e
                        logger.warning(
                            "parserService attempt %d/%d failed (%s) — retrying in %ds…",
                            _attempt, _API_MAX_RETRIES, _e, _API_RETRY_DELAY_S,
                        )
                        time.sleep(_API_RETRY_DELAY_S)
                        continue

                    api_resp = json.loads(_raw)
                    report   = api_resp.get("report", {})
                    if report:
                        logger.info("parserService responded on attempt %d", _attempt)
                        break
                    logger.warning(
                        "parserService attempt %d/%d returned empty report — retrying in %ds…",
                        _attempt, _API_MAX_RETRIES, _API_RETRY_DELAY_S,
                    )
                    time.sleep(_API_RETRY_DELAY_S)

                if api_exc is not None:
                    raise AssertionError(
                        f"parserService REST call failed after {_API_MAX_RETRIES}"
                        f" attempts: {api_exc}\nURL: {api_url}"
                    )
                if not report:
                    raise AssertionError(
                        f"parserService returned empty report after"
                        f" {_API_MAX_RETRIES} attempts: {_raw[:300] if _raw else '(no response)'}"
                    )

                logger.info("API OK  type=%s  name=%s", report.get('type'), report.get('name'))
                raw_rows = report.get("data", [])
                col_defs = list(report.get("columnDefs", []))
                # columnDefs may be incomplete — merge with actual data keys
                # so every field present in the rows is included in headers.
                if raw_rows:
                    seen = set(col_defs)
                    for k in raw_rows[0].keys():
                        if k not in seen:
                            col_defs.append(k)
                            seen.add(k)
                logger.debug("columnDefs: %s", col_defs)
                logger.info("Total rows: %d", len(raw_rows))
                for r in raw_rows:
                    logger.debug("    %s", r)

                # ── Step 7: filter rows ────────────────────────────────────
                self._step(7, "Filter rows" + (f" → '{self._device_filter}'" if self._device_filter else " (no filter)"))

                if self._device_filter:
                    filtered = [
                        r for r in raw_rows
                        if self._device_filter in r.get("Component", "")
                    ]
                    if not filtered:
                        logger.warning("No rows matched device_filter '%s' — using all rows", self._device_filter)
                        filtered = raw_rows
                else:
                    filtered = raw_rows

                logger.info("Rows after filter: %d", len(filtered))
                for r in filtered:
                    logger.debug("    %s", r)

                title_str  = (
                    f"{self._metric_name}"
                    + (f" — {self._device_filter}" if self._device_filter else "")
                )
                all_headers = ["_title"] + col_defs
                all_rows    = [{"_title": title_str, **r} for r in filtered]

                # ── Step 8: save ───────────────────────────────────────────
                self._step(8, "Save CSV and JSON")
                if all_rows and cfg.save_output:
                    csv_path, json_path = self._save_summary(all_rows, all_headers)
                else:
                    logger.warning("Skipping save (no rows or save_output=False)")

                # ── Step 9: verify thresholds ──────────────────────────────
                _labels = []
                for c, v in self._thresholds.items():
                    _labels.append(f"{c} ≥ {v}")
                for c, v in self._max_thresholds.items():
                    _labels.append(f"{c} ≤ {v/1_000_000:.0f} ms ({v:.4g} ns)")
                if _labels:
                    self._step(9, "Verify thresholds: " + ", ".join(_labels))
                else:
                    self._step(9, "No thresholds specified — skipping verification")

                verdicts, passed = self._verify_thresholds(all_rows)

                for line in verdicts:
                    logger.info("%s", line)

                if not _labels:
                    logger.info("(no threshold checks configured)")
                    passed = True
                elif passed:
                    logger.info("★ OVERALL: PASS — %s", ", ".join(_labels))
                else:
                    raise AssertionError(
                        f"FAIL — thresholds not met. Details: {verdicts}"
                    )

                return VisualizerResult(
                    metric_name=self._metric_name,
                    device_filter=self._device_filter,
                    rows=all_rows,
                    headers=all_headers,
                    csv_path=csv_path,
                    json_path=json_path,
                    verdicts=verdicts,
                    passed=passed,
                )

            except Exception as exc:
                logger.error("ERROR: %s", exc)
                raise

            finally:
                self._step(99, "Close browser")
                context.close()
                browser.close()
                logger.info("Browser closed")
