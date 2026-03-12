"""
PHM Visualizer  smoke test  (thin CLI wrapper)
================================================
實際邏輯全部在 lib/testtool/phm/visualizer.py 。
此腳本僅負責：
  1. 解析 CLI 參數
  2. 組合 VisualizerConfig
  3. 呼叫 run_visualizer_check()
  4. 印出 PASS / FAIL 並設定 exit code

執行方式
--------
  最簡（使用預設值 PCIeLPM + NVM + L1.2>=90% ）::

      python tests/verification/phm/smoke_phm_visualizer_pcie_lpm.py

  自訂參數::

      python tests/verification/phm/smoke_phm_visualizer_pcie_lpm.py \
          --metric PCIeLTR \
          --device "" \
          --threshold L1.2=90.0 --threshold L1=0.5 \
          --headless

  從程式碼呼叫 library::

      from lib.testtool.phm.visualizer import VisualizerConfig, run_visualizer_check

      result = run_visualizer_check(
          metric_name="PCIeLPM",
          device_filter="Standard NVM Express Controller",
          thresholds={"L1.2": 90.0},
          config=VisualizerConfig(headless=True),
      )
      assert result.passed, result.verdicts

CLI 參數說明
-----------
  --metric TEXT       樹狀目錄要勾選的項目（預設 PCIeLPM）
                        例：PCIeLPM / PCIeLTR
  --device TEXT       子項目 exclusive-select 字串
                        空字串 "" = 保留所有子項目，不過濾 (預設: Standard NVM Express Controller)
  --threshold COL=N   驗証欄位 >= 最小值，可重複（預設 L1.2=90.0）
                        例：--threshold L1.2=90.0 --threshold L1=0.5
  --headless          不顯示瀏覽器視窗
  --no-save           不儲存 CSV / JSON
  --host HOST         PHM web-server 主機（預設 localhost）
  --port PORT         PHM Web UI 埠號（預設 1337）
  --api-port PORT     PHM REST API 埠號（預設 1338）
  --traces-dir DIR    PHM traces 根目錄
  --output-dir DIR    CSV / JSON 輸出目錄
  --pause SECS        步驟間暫停秒數（預設 1.0）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#  make workspace root importable when run directly 
# File: tests/verification/phm/smoke_*.py    4 levels up = workspace root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.testtool.phm.visualizer import VisualizerConfig, run_visualizer_check


#  Default parameters  edit here for quick local runs 
DEFAULT_METRIC        = "PCIeLPM"
DEFAULT_DEVICE_FILTER = "Standard NVM Express Controller"
DEFAULT_THRESHOLDS    = {"L1.2": 90.0}


#  CLI 

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PHM Visualizer smoke test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--metric", default=DEFAULT_METRIC,
        help="Metric name in Visualizer tree (default: %(default)s)",
    )
    p.add_argument(
        "--device", default=DEFAULT_DEVICE_FILTER,
        help="Child item exclusive-select string; empty string keeps all",
    )
    p.add_argument(
        "--threshold", dest="thresholds", action="append", metavar="COL=VALUE",
        help="Column >= minimum-value check, repeatable (default: L1.2=90.0)",
    )
    p.add_argument("--headless",  action="store_true", help="Run browser headless")
    p.add_argument("--no-save",   action="store_true", help="Skip CSV/JSON output")
    p.add_argument("--host",      default="localhost", help="PHM host (default: %(default)s)")
    p.add_argument("--port",      type=int, default=1337, help="PHM Web UI port (default: %(default)s)")
    p.add_argument("--api-port",  type=int, default=1338, help="PHM REST API port (default: %(default)s)")
    p.add_argument("--traces-dir", default=None, help="PHM traces root directory")
    p.add_argument("--output-dir", default=None, help="Output directory for CSV/JSON")
    p.add_argument("--pause",     type=float, default=1.0, help="Pause between steps in seconds (default: %(default)s)")
    return p.parse_args()


def _build_thresholds(raw: list[str] | None) -> dict[str, float]:
    """
    Parse ``["L1.2=90.0", "L1=0.5"]``  ->  ``{"L1.2": 90.0, "L1": 0.5}``.
    Falls back to DEFAULT_THRESHOLDS when *raw* is None.
    """
    if raw is None:
        return dict(DEFAULT_THRESHOLDS)
    result: dict[str, float] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(f"--threshold must be COL=VALUE, got: {item!r}")
        col, _, val = item.partition("=")
        result[col.strip()] = float(val.strip())
    return result


#  Entry point 

def main() -> None:
    args = _parse_args()

    cfg = VisualizerConfig(
        host=args.host,
        port=args.port,
        api_port=args.api_port,
        headless=args.headless,
        pause_between_steps=args.pause,
        save_output=not args.no_save,
    )
    if args.traces_dir:
        cfg.traces_base_dir = Path(args.traces_dir)
    if args.output_dir:
        cfg.output_dir = Path(args.output_dir)

    device_filter = args.device if args.device else None
    thresholds    = _build_thresholds(args.thresholds)

    print("=" * 60)
    print(f"  metric_name   : {args.metric}")
    print(f"  device_filter : {device_filter!r}")
    print(f"  thresholds    : {thresholds}")
    print(f"  headless      : {cfg.headless}")
    print(f"  save_output   : {cfg.save_output}")
    print("=" * 60)

    result = run_visualizer_check(
        metric_name=args.metric,
        device_filter=device_filter,
        thresholds=thresholds,
        config=cfg,
    )

    print()
    if result.passed:
        print("[RESULT] PASS")
        sys.exit(0)
    else:
        print("[RESULT] FAIL")
        for v in result.verdicts:
            print(f"  {v}")
        sys.exit(1)


if __name__ == "__main__":
    main()