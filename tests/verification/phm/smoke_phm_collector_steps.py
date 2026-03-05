"""
PHM Collector — Step-by-Step Smoke Test
========================================
用途：在實際 PHM 執行中，以單步方式觀察每個 UI 操作。

執行方式
--------
直接執行（會自動走完所有步驟）::

    python tests/verification/smoke_phm_collector_steps.py

在 VS Code 中單步除錯
---------------------
1. 在任意 ``# ── Step N`` 行打斷點
2. 按 F5（Run and Debug） 啟動
3. 每按一次 F10 執行一個步驟，瀏覽器會同步反應

前提條件
--------
- PHM (PowerhouseMountain.exe) 已啟動，Web UI 在 http://localhost:1337
- 已安裝 playwright：  pip install playwright && playwright install chromium
- headless = False（預設），才能看到瀏覽器視窗

可調整的參數（腳本頂部）
------------------------
    HOST                  PHM 主機（預設 localhost）
    PORT                  PHM 埠號（預設 1337）
    HEADLESS              True = 不顯示瀏覽器視窗
    DELAYED_START_SEC     Delayed Start (seconds)
    SCENARIO_DURATION_MIN Scenario Duration (minutes)
    CYCLE_COUNT           Cycle Count
    WAIT_FOR_SERVER_SEC   最多等待 PHM server 就緒的秒數
    PAUSE_BETWEEN_STEPS   每個步驟之間暫停幾秒（方便肉眼觀察）
"""

import sys
import time
from pathlib import Path

# ── make lib importable when run directly ─────────────────────────────
# File is at tests/verification/phm/smoke_*.py  →  4 levels up = workspace root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.testtool.phm.ui_monitor import PHMUIMonitor
from lib.testtool.phm.collector_session import CollectorSession
from lib.testtool.phm.scenarios.modern_standby_cycling import (
    ModernStandbyCyclingParams,
)

# ======================================================================
# ★ 在這裡調整測試參數
# ======================================================================
HOST                  = "localhost"
PORT                  = 1337
HEADLESS              = False       # False = 顯示瀏覽器，方便觀察
DELAYED_START_SEC     = 10
SCENARIO_DURATION_MIN = 1
CYCLE_COUNT           = 3
WAIT_FOR_SERVER_SEC   = 30
PAUSE_BETWEEN_STEPS   = 1.0        # seconds; set 0 to disable


# ======================================================================
# Helper
# ======================================================================

def step(n, description: str) -> None:
    """Print a clearly visible step banner."""
    print(f"\n{'='*60}")
    print(f"  Step {n}: {description}")
    print(f"{'='*60}")
    if PAUSE_BETWEEN_STEPS > 0:
        time.sleep(PAUSE_BETWEEN_STEPS)


# ======================================================================
# Main — each numbered block is one logical step.
# Set a breakpoint on any ``step(...)`` line to pause before that action.
# ======================================================================

def main() -> None:
    ui = PHMUIMonitor(
        host=HOST,
        port=PORT,
        headless=HEADLESS,
    )

    try:
        # ── Step 1: Wait for PHM server ───────────────────────────────
        step(1, f"Wait for PHM server at http://{HOST}:{PORT}")
        ui.wait_for_ready(timeout=WAIT_FOR_SERVER_SEC)
        print(f"  ✓ Server is ready")

        # ── Step 2: Open browser ──────────────────────────────────────
        step(2, "Open Chromium browser and load PHM web UI")
        ui.open_browser(headless=HEADLESS)
        print(f"  ✓ Browser opened")

        # ── Step 3: Navigate to Collector tab ─────────────────────────
        step(3, 'Click the "Collector" tab')
        ui.navigate_to_collector()
        print(f"  ✓ Collector tab active")

        # ── Step 4: Expand Collection Options ─────────────────────────
        step(4, 'Expand "Collection Options" accordion (if not already open)')
        already_open = ui.is_collection_options_expanded()
        print(f"  ℹ Already expanded: {already_open}")
        ui.expand_collection_options()
        print(f"  ✓ Collection Options expanded")

        # ── Step 4b: Debug — dump HTML + radio elements ──────────────
        step("4b", "[DEBUG] Dump page HTML and list radio candidates")
        ui.dump_html("tmp/phm_collector_debug.html")
        ui.dump_radio_candidates(keyword="Modern Standby")
        print("  ℹ HTML saved to tmp/phm_collector_debug.html")

        # ── Step 5: Select preset scenario ────────────────────────────
        step(5, 'Select radio button: "Modern Standby Cycling"')
        ui.select_preset_scenario("Modern Standby Cycling")
        print(f"  ✓ Scenario selected and radio verified as checked")

        # ── Step 6: Set Delayed Start ─────────────────────────────────
        step(6, f"Set Delayed Start = {DELAYED_START_SEC} seconds")
        ui.set_delayed_start(DELAYED_START_SEC)
        print(f"  ✓ Delayed Start = {DELAYED_START_SEC}s")

        # ── Step 7: Set Scenario Duration ─────────────────────────────
        step(7, f"Set Scenario Duration = {SCENARIO_DURATION_MIN} minutes")
        ui.set_scenario_duration(SCENARIO_DURATION_MIN)
        print(f"  ✓ Scenario Duration = {SCENARIO_DURATION_MIN}min")

        # ── Step 8: Set Cycle Count ───────────────────────────────────
        step(8, f"Set Cycle Count = {CYCLE_COUNT}")
        ui.set_cycle_count(CYCLE_COUNT)
        print(f"  ✓ Cycle Count = {CYCLE_COUNT}")

        # ── Step 9: Click Start ───────────────────────────────────────
        step(9, "Click Start button → test begins")
        ui.start_test()
        print(f"  ✓ Start clicked — test is running")

        # ── Step 10: Watch status (optional, Ctrl-C to abort) ─────────
        step(10, 'Polling Show Log until "Data analysis finished." (Ctrl-C to skip)')
        try:
            ui.wait_for_completion(timeout=7200)
            print(f"  ✓ Test completed — 'Data analysis finished.' seen in log")
        except KeyboardInterrupt:
            print("  ⚠ Polling interrupted by user — test may still be running")

    except Exception as exc:
        print(f"\n✗ ERROR at step above: {exc}")
        raise

    finally:
        # ── Cleanup ───────────────────────────────────────────────────
        step(99, "Close browser")
        ui.close_browser()
        print("  ✓ Browser closed\n")


# ── Alternative: run as CollectorSession (uses the same steps internally) ──
def main_via_session() -> None:
    """
    Same as main() but delegates steps 3-9 to CollectorSession.run().
    Use this variant when you want to test the high-level API as a whole
    rather than each individual UI call.
    """
    params = ModernStandbyCyclingParams(
        delayed_start_seconds=DELAYED_START_SEC,
        scenario_duration_minutes=SCENARIO_DURATION_MIN,
        cycle_count=CYCLE_COUNT,
    )
    print(f"\nParams: {params}")

    ui = PHMUIMonitor(host=HOST, port=PORT, headless=HEADLESS)
    try:
        step(1, f"Wait for PHM server at http://{HOST}:{PORT}")
        ui.wait_for_ready(timeout=WAIT_FOR_SERVER_SEC)

        step(2, "Open browser")
        ui.open_browser()

        step(3, "CollectorSession.run() → performs steps 3-9 atomically")
        session = CollectorSession(ui)
        session.run(params)
        print("  ✓ CollectorSession.run() completed — test is running")

        step(4, "Polling completion (Ctrl-C to skip)")
        try:
            ui.wait_for_completion(timeout=7200)
        except KeyboardInterrupt:
            print("  ⚠ Interrupted")
    finally:
        ui.close_browser()


# ======================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PHM Collector step-by-step smoke test"
    )
    parser.add_argument(
        "--session",
        action="store_true",
        help="Use CollectorSession.run() (high-level) instead of individual steps",
    )
    args = parser.parse_args()

    if args.session:
        main_via_session()
    else:
        main()
