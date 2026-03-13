"""
PHM Visualizer -- SoC S0ix Substates smoke test
=================================================
tree    : SoC S0ix Substates  (parent, checked + expanded)
sub-item: SoC S0ix Substrates (exclusively selected child)
verify  : s0i2.2 Residency >= 90  (%)

columns : Component | s0i2.0 Residency | s0i2.1 Residency | s0i2.2 Residency | Not In SLP_S0

CLI
---
  python tests/verification/phm/smoke_phm_visualizer_soc_s0ix_substates.py
  python tests/verification/phm/smoke_phm_visualizer_soc_s0ix_substates.py \\
      --threshold "s0i2.2 Residency=95" --headless
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.testtool.phm.visualizer import VisualizerConfig, run_visualizer_check

# ── Test parameters ──────────────────────────────────────────────────────────
METRIC          = "SoC S0ix Substates"   # sidebar parent node label
DEVICE_FILTER   = "SoC S0ix Substrates"  # child sub-item to exclusively select
API_METRIC_NAME = "SoC S0ix Substates"   # REST API ``name=`` parameter (parent category)

# Lower-bound checks   (column >= value)
THRESHOLDS: dict[str, float] = {"s0i2.2 Residency": 90.0}

# Upper-bound checks   (column <= value)  — not required for this metric
MAX_THRESHOLDS: dict[str, float] = {}


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description=f"PHM Visualizer {METRIC}/{DEVICE_FILTER} smoke test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--threshold", dest="thresholds", action="append",
                   metavar="COL=VALUE",
                   help='Lower-bound check: column >= value, repeatable '
                        '(default: "s0i2.2 Residency=90.0")')
    p.add_argument("--max-threshold", dest="max_thresholds", action="append",
                   metavar="COL=VALUE",
                   help="Upper-bound check: column <= value, repeatable")
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
    print(f"  device_filter   : {DEVICE_FILTER!r}")
    print(f"  api_metric_name : {API_METRIC_NAME}")
    print(f"  thresholds      : {thresholds}")
    print(f"  max_thresholds  : {max_thresholds}")
    print(f"  headless        : {cfg.headless}")
    print(f"  save_output     : {cfg.save_output}")
    print("=" * 60)

    result = run_visualizer_check(
        metric_name=METRIC,
        device_filter=DEVICE_FILTER,
        api_metric_name=API_METRIC_NAME,
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
