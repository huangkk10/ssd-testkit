# PHM Web UI — Quick Automation Guide

- **Automation method**: Use Playwright (Python sync API). PHM runs a Node.js web UI at `http://localhost:1337`.
- **Primary selectors**:
  - Preset radios: use attribute id selector — `[id="chk_coll_sc_{Scenario Name}"]` (IDs may contain spaces).
  - Preset labels: `[id="lbl_coll_sc_{Scenario Name}"]`.
  - Per-scenario counter host: `id="app-collector-{scenario_short}-cnt_coll_op_{Option Name}"` with child `input.counter-field` for the numeric input.
  - Show Log textarea: `[id="textArea_daq_logSummary"]` (read with `.input_value()`).
  - Status/banner with traces info: `[id="lbl_coll_statusMsg"]` contains `Traces saved to <path>`.
- **Common workflow**:
  1. Navigate to Collector tab (`http://localhost:1337` → open Collector view).
  2. Select preset scenario by clicking the radio: click the radio locator then verify `.is_checked()`.
  3. Expand "Collection Options" accordion if collapsed.
  4. Set numeric counters (Delayed Start / Scenario Duration / Cycle Count) by targeting the host id, focusing the `input.counter-field`, using `click(click_count=3)` to select existing value, `page.fill()` or `page.type()`, and dispatching `input`/`change` events if needed.
  5. Click Start and then poll the Show Log for the sentinel `Data analysis finished.` to detect run completion.
  6. After completion, read `[id="lbl_coll_statusMsg"]` and extract the substring after `Traces saved to ` to obtain the traces folder path.
- **Robustness & debugging tips**:
  - Use exact attribute id selectors (`[id="..."]`) because IDs contain spaces and special chars.
  - Always verify state after action (e.g., `.is_checked()` for radios, `.input_value()` for inputs).
  - If selectors fail, save the page HTML (`page.content()` → tmp file) and run a local ID-extraction script to confirm actual ids.
  - Prefer waiting for visibility/stability before interacting (`locator.wait_for(state="visible")`).
  - For numeric counters, triple-click semantics are `click(click_count=3)` in Playwright; `triple_click()` is not available.
  - When test runs finish, the PHM status label contains the traces path; copy the traces directory into your verification folder for archiving using `shutil.copytree()`.
- **Reference implementation**: See `lib/testtool/phm/ui_monitor.py` for helper methods: `select_preset_scenario()`, `expand_collection_options()`, `_fill_counter_field()`, `get_log_text()`, `wait_for_completion()`, and `get_traces_path()`.
