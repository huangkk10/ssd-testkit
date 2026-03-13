"""
PHM Visualizer  PCIe LTR "Standard NVM Express Controller" smoke test
=======================================================================
metric  : PCIe LTR  (tree label; REST API also accepts "PCIe LTR")
device  : Standard NVM Express Controller
verify  : Min LTR value <= 50 ms  (50,000,000 ns)
          Values reported as "No LTR" are skipped (no measurement).

執行方式
--------
  python tests/verification/phm/smoke_phm_visualizer_pcie_ltr.py

  覆寫 threshold::

      python tests/verification/phm/smoke_phm_visualizer_pcie_ltr.py \
          --max-threshold Min=30000000 --headless
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.testtool.phm.visualizer import VisualizerConfig, run_visualizer_check

#  Test parameters 
# PHM sidebar tree label is "PCIe LTR" (with space).
METRIC          = "PCIe LTR"
API_METRIC_NAME = "PCIe LTR"
DEVICE_FILTER   = "Standard NVM Express Controller"

# Lower-bound checks  (column >= value)  not applicable for LTR
THRESHOLDS: dict[str, float] = {}

# Upper-bound checks  (column <= value, unit = ns)
# Min LTR must be < 50 ms = 50,000,000 ns
# Non-numeric values (e.g. "No LTR") are automatically skipped.
MAX_THRESHOLDS: dict[str, float] = {"Min": 50_000_000}


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description=f"PHM Visualizer {METRIC} smoke test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--max-threshold", dest="max_thresholds", action="append",
                   metavar="COL=VALUE_NS",
                   help="Upper-bound check: column <= value (in ns), repeatable "
                        "(default: Min=50000000)")
    p.add_argument("--threshold", dest="thresholds", action="append",
                   metavar="COL=VALUE",
                   help="Lower-bound check: column >= value, repeatable")
    p.add_argument("--headless",   action="store_true")
    p.add_argument("--no-save",    action="store_true")
    p.add_argument("--host",       default="localhost")
    p.add_argument("--port",       type=int, default=1337)
    p.add_argument("--api-port",   type=int, default=1338)
    p.add_argument("--traces-dir", default=None)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--pause",      type=float, default=1.0)
    args = p.parse_args()

    def _parse_kv(items: list[str] | None, defaults: dict) -> dict[str, float]:
        if items is None:
            return dict(defaults)
        result: dict[str, float] = {}
        for item in items:
            col, _, val = item.partition("=")
            result[col.strip()] = float(val.strip())
        return result

    thresholds     = _parse_kv(args.thresholds,     THRESHOLDS)
    max_thresholds = _parse_kv(args.max_thresholds, MAX_THRESHOLDS)

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

    print("=" * 60)
    print(f"  metric_name     : {METRIC}")
    print(f"  api_metric_name : {API_METRIC_NAME}")
    print(f"  device_filter   : {DEVICE_FILTER!r}")
    print(f"  thresholds      : {thresholds}")
    print(f"  max_thresholds  : {max_thresholds}  (ns)")
    print(f"  headless        : {cfg.headless}")
    print(f"  save_output     : {cfg.save_output}")
    print("=" * 60)

    result = run_visualizer_check(
        metric_name=METRIC,
        api_metric_name=API_METRIC_NAME,
        device_filter=DEVICE_FILTER,
        thresholds=thresholds,
        max_thresholds=max_thresholds,
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