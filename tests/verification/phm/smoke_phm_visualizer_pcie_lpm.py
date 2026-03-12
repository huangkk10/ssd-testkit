"""
PHM Visualizer — PCIeLPM "Standard NVM Express Controller" Summary Test
=======================================================================
用途：
  1. 開啟 PHM Web UI（http://localhost:1337）
  2. 點擊 Open Trace 按鈕 → 選擇最新 Scenario 資料夾的 Contents.cycl
  3. 在 CycleSummary 頁點擊綠色的 Content.phm 路徑連結
  4. 切換到 Visualizer 側邊 tab
  5. 勾選 PCIeLPM checkbox，展開後勾選含 "Standard NVM Express Controller" 的項目
  6. 點擊 Show Summary 按鈕，擷取並儲存表格資料（CSV + JSON）

執行方式
--------
直接執行::

    python tests/verification/phm/smoke_phm_visualizer_pcie_lpm.py

可調整的參數（腳本頂部）
------------------------
    HOST              PHM 主機（預設 localhost）
    PORT              PHM 埠號（預設 1337）
    HEADLESS          True = 不顯示瀏覽器視窗
    TRACES_BASE_DIR   PHM traces 根目錄
    OUTPUT_DIR        儲存 CSV / JSON 的目錄
    PAUSE_BETWEEN_STEPS  每步驟間暫停秒數（肉眼觀察用）
"""

import csv
import json
import sys
import time
import urllib.request
import urllib.parse as _urlparse
from pathlib import Path

# ── make lib importable when run directly ────────────────────────────────────
# File is at tests/verification/phm/smoke_*.py  →  4 levels up = workspace root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeoutError
    _PW_OK = True
except ImportError:
    _PW_OK = False
    print("[WARN] playwright not installed — run: pip install playwright && playwright install chromium")

# ======================================================================
# ★ 在這裡調整測試參數
# ======================================================================
HOST                = "localhost"
PORT                = 1337
HEADLESS            = False          # False = 顯示瀏覽器，方便觀察
TRACES_BASE_DIR     = Path(r"C:\Program Files\PowerhouseMountain\traces")
OUTPUT_DIR          = Path(__file__).parent / "output"
PAUSE_BETWEEN_STEPS = 1.0            # seconds; set 0 to disable


# ======================================================================
# Helpers
# ======================================================================

def step(n, description: str) -> None:
    """Print a clearly visible step banner."""
    print(f"\n{'='*60}")
    print(f"  Step {n}: {description}")
    print(f"{'='*60}")
    if PAUSE_BETWEEN_STEPS > 0:
        time.sleep(PAUSE_BETWEEN_STEPS)


def find_latest_scenario_dir(traces_base: Path) -> Path:
    """Return the newest Scenario* sub-directory under *traces_base*."""
    scenarios = sorted(
        [d for d in traces_base.iterdir() if d.is_dir() and d.name.startswith("Scenario")],
        key=lambda d: d.name,
    )
    if not scenarios:
        raise FileNotFoundError(f"No Scenario* folders found under {traces_base}")
    latest = scenarios[-1]
    print(f"  ℹ Latest scenario folder : {latest}")
    # Print all scenario folders found for context
    print(f"  ℹ All scenario folders ({len(scenarios)})")
    for s in scenarios[-5:]:   # show last 5
        print(f"      {s.name}")
    return latest


def find_contents_cycl(scenario_dir: Path) -> Path:
    """
    Locate Contents.cycl inside *scenario_dir*.
    PHM typically places it directly at the scenario root; fall back to
    recursive search if not found there.
    """
    # 1. Direct location (most common — matches PHM viewtrace URL pattern)
    direct = scenario_dir / "Contents.cycl"
    if direct.exists():
        print(f"  ℹ Contents.cycl found (direct): {direct}")
        return direct

    # 2. Recursive search
    found = list(scenario_dir.rglob("Contents.cycl"))
    if not found:
        raise FileNotFoundError(f"Contents.cycl not found anywhere under {scenario_dir}")
    if len(found) > 1:
        print(f"  ⚠ Multiple Contents.cycl found — using first:")
        for f in found:
            print(f"      {f}")
    chosen = found[0]
    print(f"  ℹ Contents.cycl found (recursive): {chosen}")
    return chosen


def build_viewtrace_url(contents_cycl: Path) -> str:
    """
    Build the PHM viewtrace URL for the given Contents.cycl path.

    URL pattern observed from PHM UI:
      http://localhost:1337/viewtrace/?pathname=opentrace&traceDir=<Contents.cycl path>
    """
    return (
        f"http://{HOST}:{PORT}/viewtrace/"
        f"?pathname=opentrace&traceDir={contents_cycl}"
    )


def _dump_debug(page: "Page", label: str) -> None:
    """Save page HTML + screenshot for post-mortem debugging."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT_DIR / f"debug_{label}.html"
    png_path  = OUTPUT_DIR / f"debug_{label}.png"
    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(png_path), full_page=True)
    print(f"  \u2139 [DEBUG] HTML  \u2192 {html_path}")
    print(f"  \u2139 [DEBUG] Screenshot \u2192 {png_path}")


def save_summary(rows: list[dict], headers: list[str]) -> Path:
    """Save table rows as CSV and JSON files, return the CSV path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    csv_path  = OUTPUT_DIR / f"pcie_lpm_summary_{timestamp}.csv"
    json_path = OUTPUT_DIR / f"pcie_lpm_summary_{timestamp}.json"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"  ✓ CSV  saved → {csv_path}")
    print(f"  ✓ JSON saved → {json_path}")
    return csv_path


# ======================================================================
# Main
# ======================================================================

def main() -> None:
    if not _PW_OK:
        sys.exit(1)

    # ── Pre-step: Find latest Scenario folder on filesystem ──────────────
    step(0, "Locate latest Scenario folder and Contents.cycl")
    latest_scenario = find_latest_scenario_dir(TRACES_BASE_DIR)
    contents_cycl   = find_contents_cycl(latest_scenario)
    print(f"  ✓ Contents.cycl path : {contents_cycl}")
    print(f"  ✓ Scenario folder    : {latest_scenario}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page    = context.new_page()

        try:
            # ── Step 1: Open PHM and click "Open Trace" ─────────────────────
            step(1, f"Open PHM UI at http://{HOST}:{PORT} and click Open Trace")
            page.goto(f"http://{HOST}:{PORT}", wait_until="networkidle", timeout=30_000)
            print(f"  ✓ PHM UI loaded")

            # Try clicking "Open Trace" button; PHM may open a file-chooser or
            # navigate to the viewtrace URL directly.
            open_trace_btn = page.locator(
                'button:has-text("Open Trace"), '
                'a:has-text("Open Trace"), '
                '[data-testid="open-trace"]'
            ).first

            # Some PHM builds open a native/web file-chooser; intercept it.
            try:
                with page.expect_file_chooser(timeout=5_000) as fc_info:
                    open_trace_btn.click(timeout=10_000)
                file_chooser = fc_info.value
                file_chooser.set_files(str(contents_cycl))
                print(f"  ✓ File chooser handled — set {contents_cycl}")
                # Wait for navigation to viewtrace page
                page.wait_for_url("**/viewtrace/**", timeout=15_000)
            except PWTimeoutError:
                # No file-chooser appeared — fall back to direct URL navigation
                print("  ℹ No file-chooser detected; navigating to viewtrace URL directly")
                viewtrace_url = build_viewtrace_url(contents_cycl)
                print(f"  → {viewtrace_url}")
                page.goto(viewtrace_url, wait_until="networkidle", timeout=30_000)

            print(f"  ✓ Viewtrace page loaded: {page.url}")

            # SPA may still be rendering — give Angular/JS time to paint
            page.wait_for_timeout(3_000)
            print(f"  ℹ Page title: {page.title()}")

            # ── DEBUG: dump HTML and screenshot right after load ──────────
            _dump_debug(page, "after_viewtrace_load")

            # ── Step 2: Click the green Content.phm path link ───────────────
            step(2, "Click the green Content.phm path link in CycleSummary")

            # --- Debug: print all <a> links and any element containing ".phm" ---
            print("  ℹ [DEBUG] All <a> href on page:")
            for href in page.eval_on_selector_all("a", "els => els.map(e => e.href + ' | ' + e.innerText.trim().slice(0,80))"):
                print(f"      {href}")

            print("  ℹ [DEBUG] Elements whose text contains '.phm':")
            for txt in page.eval_on_selector_all(
                "*", "els => els.filter(e => e.children.length === 0 && e.innerText && e.innerText.includes('.phm')).map(e => e.tagName + '|' + e.className + '|' + e.innerText.trim().slice(0,120))"
            )[:20]:  # cap at 20
                print(f"      {txt}")

            # Broad locator: any element (leaf node) whose visible text contains
            # 'Content.phm' — PHM renders the green path as a clickable row or link.
            # We try multiple strategies in order of specificity.
            phm_link = (
                page.locator("a").filter(has_text="Content.phm").first
                if page.locator("a").filter(has_text="Content.phm").count() > 0
                else page.locator("[class*='green'], [style*='color: green'], [style*='color:green']").filter(has_text=".phm").first
                if page.locator("[class*='green'], [style*='color: green'], [style*='color:green']").filter(has_text=".phm").count() > 0
                else page.get_by_text("Content.phm", exact=False).first
            )

            phm_link.wait_for(state="visible", timeout=15_000)
            phm_text = phm_link.inner_text().strip()
            print(f"  ℹ Found link text: {phm_text}")
            phm_link.click()
            print(f"  ✓ Content.phm link clicked")

            # Wait for the trace data to fully load
            page.wait_for_load_state("networkidle", timeout=30_000)
            page.wait_for_timeout(2_000)

            # ── Step 3: Switch to Visualizer tab ─────────────────────────────
            step(3, "Click the Visualizer tab in the left sidebar")
            # Use JS click-by-title — same approach confirmed working in capture_popup.py.
            # Playwright locator 'button:has-text("Visualizer")' was landing on the
            # Diagnostics tab instead.  Matching by title is unambiguous.
            vis_clicked = page.evaluate("""() => {
                const btn = [...document.querySelectorAll('button')]
                    .find(b => b.title === 'Visualize metrics in a timeline');
                if (btn) { btn.click(); return btn.title; }
                // fallback: button whose text is exactly 'Visualizer'
                const btn2 = [...document.querySelectorAll('button')]
                    .find(b => (b.innerText || '').trim() === 'Visualizer');
                if (btn2) { btn2.click(); return 'Visualizer (by text)'; }
                return null;
            }""")
            assert vis_clicked, (
                "Could not find Visualizer tab button. "
                "Check that PHM Visualizer is available for this trace."
            )
            print(f"  ✓ Visualizer tab clicked: {vis_clicked}")
            page.wait_for_timeout(2_000)  # let tree and canvas start rendering

            # ── DEBUG: dump Visualizer HTML + print checkbox elements ───
            _dump_debug(page, "after_visualizer_tab")

            print("  ℹ [DEBUG] All checkbox-like elements:")
            for info in page.eval_on_selector_all(
                "input[type='checkbox'], mat-checkbox, [role='checkbox'], "
                "[class*='checkbox'], [class*='check-box']",
                "els => els.map(e => ({"
                "  tag: e.tagName,"
                "  cls: e.className.slice(0,80),"
                "  role: e.getAttribute('role') || '',"
                "  checked: e.checked !== undefined ? e.checked : e.getAttribute('aria-checked'),"
                "  text: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0,80)"
                "}))"
            ):
                print(f"      {info}")

            print("  ℹ [DEBUG] Elements whose visible text contains 'PCIeLPM':")
            for info in page.eval_on_selector_all(
                "*",
                "els => els"
                "  .filter(e => e.children.length === 0 && (e.innerText||'').includes('PCIeLPM'))"
                "  .map(e => e.tagName+'|'+e.className.slice(0,60)+'|'+e.innerText.trim().slice(0,100))"
            ):
                print(f"      {info}")

            # ── Step 4: Check PCIeLPM checkbox and expand it ─────────────────
            step(4, "Check PCIeLPM checkbox and expand its children")

            def _tree_item_info(text: str) -> dict | None:
                """
                Return checked + expanded state of a tree-label row whose
                ng-binding span contains *text*.  Returns None if not found.
                """
                return page.evaluate(
                    """(text) => {
                        for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                            const lbl = row.querySelector('button.tree-label');
                            if (!lbl) continue;
                            const nb = lbl.querySelector('span.ng-binding');
                            if (!nb || !nb.innerText.includes(text)) continue;
                            const checked  = !!lbl.querySelector('span.glyphicon-check');
                            const expanded = !!row.querySelector(
                                'i.glyphicon-triangle-bottom');
                            return {
                                checked,
                                expanded,
                                label: nb.innerText.trim().slice(0, 80),
                            };
                        }
                        return null;
                    }""",
                    text,
                )

            def _tree_check(text: str) -> bool:
                """
                Ensure the tree row for *text* is CHECKED.
                Only clicks if currently unchecked.  Returns True if found.
                """
                return page.evaluate(
                    """(text) => {
                        for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                            const lbl = row.querySelector('button.tree-label');
                            if (!lbl) continue;
                            const nb = lbl.querySelector('span.ng-binding');
                            if (!nb || !nb.innerText.includes(text)) continue;
                            const checked = !!lbl.querySelector('span.glyphicon-check');
                            if (!checked) {
                                lbl.click();
                                return 'clicked (was unchecked)';
                            }
                            return 'skipped (already checked)';
                        }
                        return null;
                    }""",
                    text,
                )

            def _tree_expand(text: str) -> bool:
                """
                Expand the tree row for *text* by clicking its triangle button.
                Skips if already expanded.  Returns True if found.
                """
                return page.evaluate(
                    """(text) => {
                        for (const row of document.querySelectorAll('tr.tree-grid-row')) {
                            const lbl = row.querySelector('button.tree-label');
                            if (!lbl) continue;
                            const nb = lbl.querySelector('span.ng-binding');
                            if (!nb || !nb.innerText.includes(text)) continue;
                            // already expanded?
                            if (row.querySelector('i.glyphicon-triangle-bottom')) {
                                return 'skipped (already expanded)';
                            }
                            const expandBtn = row.querySelector('button.tree-icon');
                            if (expandBtn) { expandBtn.click(); return 'expanded'; }
                            return 'no expand button';
                        }
                        return null;
                    }""",
                    text,
                )

            def _tree_set_exclusive(parent_text: str, keep_text: str) -> list:
                """
                Among the DIRECT children of *parent_text* in the sidebar tree,
                ensure ONLY the child whose label contains *keep_text* is checked.
                All other children are unchecked.

                Depth detection strategy: PHM applies indentation via CSS class only
                (not inline style), so padding-left is unusable.  Instead we rely on
                the structural fact that parent-level (expandable) rows contain a
                ``button.tree-icon`` element, while leaf child rows contain only
                ``button.tree-label``.  We iterate rows after the parent and stop
                as soon as we encounter another row that has a tree-icon button
                (= the next sibling group).

                Returns a list of action strings for logging.
                """
                return page.evaluate(
                    """([parentText, keepText]) => {
                        const rows = [...document.querySelectorAll('tr.tree-grid-row')];

                        // Find the parent row (exact label match)
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

                            // A row with tree-icon is an expandable parent-level node
                            // → we've left the children scope, stop.
                            if (row.querySelector('button.tree-icon')) break;

                            const lbl = row.querySelector('button.tree-label');
                            if (!lbl) continue;
                            const nb = lbl.querySelector('span.ng-binding');
                            if (!nb) continue;

                            const text    = nb.innerText.trim();
                            const checked = !!lbl.querySelector('span.glyphicon-check');

                            if (text.includes(keepText)) {
                                if (!checked) {
                                    lbl.click();
                                    results.push('checked: ' + text.slice(0, 70));
                                } else {
                                    results.push('kept:    ' + text.slice(0, 70));
                                }
                            } else {
                                if (checked) {
                                    lbl.click();
                                    results.push('unchecked: ' + text.slice(0, 70));
                                }
                                // else already unchecked — no action needed
                            }
                        }
                        return results.length
                            ? results
                            : ['no children found or no changes needed'];
                    }""",
                    [parent_text, keep_text],
                )

            # --- Check current state of PCIeLPM ---
            info = _tree_item_info("PCIeLPM")
            print(f"  ℹ PCIeLPM state before action: {info}")

            # Ensure PCIeLPM is CHECKED
            result = _tree_check("PCIeLPM")
            print(f"  ℹ PCIeLPM check result: {result}")

            # Expand PCIeLPM to show children
            result = _tree_expand("PCIeLPM")
            print(f"  ℹ PCIeLPM expand result: {result}")
            page.wait_for_timeout(1_500)  # wait for child rows to render

            # ── Step 5: Uncheck all PCIeLPM children except NVM ──────────────
            step(5, 'Keep ONLY "Standard NVM Express Controller" checked under PCIeLPM')

            actions = _tree_set_exclusive(
                "PCIeLPM",
                "Standard NVM Express Controller",
            )
            print(f"  ℹ Exclusive-select actions ({len(actions)}):")
            for a in actions:
                print(f"      {a}")

            # Give Angular time to process the clicks before reading final state
            page.wait_for_timeout(800)

            # Verify final state
            nvm_info = _tree_item_info("Standard NVM Express Controller")
            print(f"  ℹ NVM final state: {nvm_info}")
            if nvm_info and not nvm_info["checked"]:
                print("  ⚠ NVM still unchecked after exclusive-select! Force-checking...")
                _tree_check("Standard NVM Express Controller")

            # ── Wait for canvas to have non-zero dimensions (up to 12 seconds) ──
            print("  ℹ Waiting for canvas to render...")
            canvas_ready = False
            for _i in range(24):               # 24 × 500 ms = 12 s
                _bb = page.evaluate("""() => {
                    const c = document.querySelector('canvas#pageCanvas0, canvas');
                    if (!c) return null;
                    const r = c.getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                }""")
                if _bb and _bb["width"] > 0:
                    print(f"  ✓ Canvas ready after {_i * 0.5:.1f}s: {_bb}")
                    canvas_ready = True
                    break
                page.wait_for_timeout(500)
            if not canvas_ready:
                _dump_debug(page, "canvas_wait_timeout")
                raise AssertionError(
                    "Canvas did not render within 12 seconds after Step 5. "
                    "See canvas_wait_timeout.png for current page state."
                )


            # ── Step 6: 呼叫 parserService REST API 取得 PCIeLPM summary ───────
            step(6, "Call parserService REST API for PCIeLPM summary")

            # Investigation (intercept_api.py) confirmed that the ic_chart button
            # internally calls:
            #   GET http://localhost:1338/parserService?target=getSummaryData
            #       &url=<phm_path>&name=PCIeLPM&minTime=0&maxTime=<big>
            # Response: {"report": {"type": 1, "name": "PCIeLPM",
            #            "data": [{"Component": ..., "Min": ..., ...}],
            #            "columnDefs": [...]}}
            # Calling this directly is far more reliable than canvas clicks.

            PHM_API_PORT = 1338

            # Locate Content.phm: <scenario>/Cycle1/Content.phm  (try all Cycle* dirs)
            phm_file: Path | None = None
            for cycle_dir in sorted(latest_scenario.glob("Cycle*/Content.phm")):
                phm_file = cycle_dir
                break
            assert phm_file and phm_file.exists(), (
                f"Content.phm not found under {latest_scenario}"
            )
            print(f"  ℹ PHM file: {phm_file}")

            encoded_path = _urlparse.quote(str(phm_file), safe="")
            api_url = (
                f"http://localhost:{PHM_API_PORT}/parserService"
                f"?target=getSummaryData"
                f"&url={encoded_path}"
                f"&name=PCIeLPM"
                f"&minTime=0"
                f"&maxTime=1844674407370950000"  # sentinel = full trace
            )
            print(f"  ℹ API URL: {api_url[:140]}...")

            try:
                with urllib.request.urlopen(api_url, timeout=15) as _resp:
                    _raw = _resp.read().decode("utf-8")
            except Exception as _e:
                raise AssertionError(
                    f"parserService REST call failed: {_e}\nURL: {api_url}"
                )

            api_resp = json.loads(_raw)
            report   = api_resp.get("report", {})
            if not report:
                raise AssertionError(
                    f"parserService returned empty report: {_raw[:300]}"
                )

            print(f"  ✓ API OK  type={report.get('type')}  name={report.get('name')}")
            print(f"  ℹ columnDefs : {report.get('columnDefs', [])}")

            raw_rows  = report.get("data", [])
            col_defs  = report.get("columnDefs", [])
            if not col_defs and raw_rows:
                col_defs = list(raw_rows[0].keys())
            print(f"  ℹ Total rows in API response: {len(raw_rows)}")
            for r in raw_rows:
                print(f"      {r}")

            # ── Step 7: Filter to Standard NVM row(s) ─────────────────────────────
            step(7, "Filter to Standard NVM Express Controller row")

            nvm_rows = [
                r for r in raw_rows
                if "Standard NVM" in r.get("Component", "")
            ]
            if not nvm_rows:
                print("  ⚠ No 'Standard NVM' row in API response — using all rows")
                nvm_rows = raw_rows

            print(f"  ✓ NVM row(s): {len(nvm_rows)}")
            for r in nvm_rows:
                print(f"      {r}")

            # 活用 getSummaryData 詞典中的 columnDefs 作為 header
            title_str = f"PCIeLPM — Standard NVM Express Controller"
            all_headers: list[str] = ["_title"] + col_defs
            all_rows: list[dict]   = [
                {"_title": title_str, **r} for r in nvm_rows
            ]

            if not all_rows:
                print("  ⚠ No rows to save")
            else:
                print(f"  ✓ Prepared {len(all_rows)} row(s) for save")

            # ── Step 8: Save the data ──────────────────────────────────────────
            step(8, "Save table data to CSV and JSON")
            if all_rows:
                save_summary(all_rows, all_headers)
            else:
                print("  ⚠ Skipping save — no data to write")

            # ── Step 9: Verify L1.2 ≥ 90 % ────────────────────────────────────
            step(9, "Verify L1.2 residency ≥ 90 % for Standard NVM Express Controller")

            L12_THRESHOLD = 90.0
            verdict_pass  = True
            verdict_lines = []

            if not all_rows:
                verdict_pass = False
                verdict_lines.append("  ✗ No data rows to evaluate")
            else:
                for row in all_rows:
                    comp   = row.get("Component", row.get("_title", "?"))
                    l12_raw = row.get("L1.2", None)
                    if l12_raw is None:
                        verdict_pass = False
                        verdict_lines.append(
                            f"  ✗ 'L1.2' column not found in row: {comp}"
                        )
                        continue
                    try:
                        l12_val = float(l12_raw)
                    except (ValueError, TypeError):
                        verdict_pass = False
                        verdict_lines.append(
                            f"  ✗ 'L1.2' value cannot be parsed as float: "
                            f"'{l12_raw}'  ({comp})"
                        )
                        continue

                    if l12_val >= L12_THRESHOLD:
                        verdict_lines.append(
                            f"  ✓ PASS  L1.2 = {l12_val:.2f} % ≥ {L12_THRESHOLD} %"
                            f"  [{comp}]"
                        )
                    else:
                        verdict_pass = False
                        verdict_lines.append(
                            f"  ✗ FAIL  L1.2 = {l12_val:.2f} % < {L12_THRESHOLD} %"
                            f"  [{comp}]"
                        )

            for line in verdict_lines:
                print(line)

            if verdict_pass:
                print(f"\n  ★ OVERALL: PASS — L1.2 ≥ {L12_THRESHOLD} %")
            else:
                raise AssertionError(
                    f"FAIL — L1.2 residency did not meet the {L12_THRESHOLD} % threshold. "
                    f"Details: {verdict_lines}"
                )

        except Exception as exc:
            print(f"\n✗ ERROR at step above: {exc}")
            raise

        finally:
            step(99, "Close browser")
            context.close()
            browser.close()
            print("  ✓ Browser closed\n")


# ======================================================================
if __name__ == "__main__":
    main()
