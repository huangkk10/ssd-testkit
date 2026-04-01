"""
OsConfig CLI Tool
=================

Standalone command-line tool to apply, revert, reset, or inspect OS
configuration settings on the current machine without needing pytest.

Typical usage
-------------
.. code-block:: bat

    # Apply settings from yaml (saves snapshot for later revert)
    python tools/osconfig/osconfig_tool.py apply --config tools/osconfig/osconfig.yaml

    # Revert to the state captured at last apply
    python tools/osconfig/osconfig_tool.py revert

    # Reset every setting back to Windows out-of-box defaults (no snapshot needed)
    python tools/osconfig/osconfig_tool.py reset

    # Show current state vs yaml targets (read-only)
    python tools/osconfig/osconfig_tool.py status --config tools/osconfig/osconfig.yaml

Purpose
-------
Quick recovery when OS settings get corrupted during development.  All
logic is delegated to ``lib/testtool/osconfig/`` — this script is a thin
CLI wrapper.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap sys.path so the script works from any cwd
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from lib.testtool.osconfig.controller import OsConfigController
from lib.testtool.osconfig.config import OsConfigProfile
from lib.testtool.osconfig.profile_loader import load_profile
from lib.testtool.osconfig.state_manager import OsConfigStateManager
from lib.testtool.osconfig.actions.auto_admin_logon import AutoAdminLogonAction

# ---------------------------------------------------------------------------
# Default snapshot path (same as used by test framework)
# ---------------------------------------------------------------------------
_DEFAULT_SNAPSHOT = (
    Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "osconfig_snapshot.json"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin() -> bool:
    """Return True when the process is running as Administrator."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _require_admin() -> None:
    if not _is_admin():
        print("ERROR: This tool requires Administrator privileges.")
        print("       Right-click the script / terminal and choose 'Run as administrator'.")
        sys.exit(1)


def _load_profile(args: argparse.Namespace) -> OsConfigProfile:
    """Resolve profile from --config / --default / auto-discover osconfig.yaml."""
    if getattr(args, "default_profile", False):
        print("[profile] Using OsConfigProfile.default()")
        return OsConfigProfile.default()

    config_path: Path | None = None
    if getattr(args, "config", None):
        config_path = Path(args.config)
    else:
        # Auto-discover: look for osconfig.yaml next to this script
        candidate = _HERE / "osconfig.yaml"
        if candidate.exists():
            config_path = candidate
            print(f"[profile] Auto-discovered: {config_path}")

    if config_path is None:
        print("ERROR: No --config specified and no osconfig.yaml found next to this script.")
        print("       Use --config <path> or --default.")
        sys.exit(1)

    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    print(f"[profile] Loading: {config_path}")
    return load_profile(config_path)


def _make_controller(
    profile: OsConfigProfile,
    snapshot_path: Path | None = None,
) -> OsConfigController:
    path = snapshot_path or _DEFAULT_SNAPSHOT
    state_manager = OsConfigStateManager(path=path)
    return OsConfigController(profile=profile, state_manager=state_manager)


def _print_results(results: dict, label: str = "Result") -> None:
    """Pretty-print a name → status dict."""
    if not results:
        print("  (no actions)")
        return
    col = max(len(k) for k in results) + 2
    for name, status in results.items():
        icon = {
            "applied":          "✓",
            "reverted":         "✓",
            "reset":            "✓",
            "skipped":          "–",
            "unsupported":      "~",
            "skip_revert":      "–",
            "not_implemented":  "?",
        }.get(status, "✗" if status.startswith("error") else "·")
        print(f"  {icon}  {name:<{col}} {status}")


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_apply(args: argparse.Namespace) -> None:
    _require_admin()
    profile = _load_profile(args)
    snapshot_path = Path(args.snapshot) if getattr(args, "snapshot", None) else _DEFAULT_SNAPSHOT
    state_manager = OsConfigStateManager(path=snapshot_path)

    if state_manager.exists() and not getattr(args, "force", False):
        print(f"WARNING: A snapshot already exists at: {snapshot_path}")
        print("         Run 'revert' first, or re-run with --force to overwrite.")
        sys.exit(1)

    controller = OsConfigController(profile=profile, state_manager=state_manager)
    print("\nApplying OS configuration …\n")
    results = controller.apply_all()
    _print_results(results)
    print(f"\nSnapshot saved → {snapshot_path}")


def cmd_revert(args: argparse.Namespace) -> None:
    _require_admin()
    snapshot_path = Path(args.snapshot) if getattr(args, "snapshot", None) else _DEFAULT_SNAPSHOT
    state_manager = OsConfigStateManager(path=snapshot_path)

    if not state_manager.exists():
        print(f"ERROR: No snapshot found at: {snapshot_path}")
        print("       Run 'apply' first to capture a snapshot.")
        sys.exit(1)

    # Build profile from yaml if given; otherwise use default so all known
    # actions are constructed (the snapshot drives the actual values restored).
    if getattr(args, "config", None):
        profile = load_profile(Path(args.config))
    else:
        profile = OsConfigProfile.default()

    controller = OsConfigController(profile=profile, state_manager=state_manager)
    print("\nReverting OS configuration …\n")
    results = controller.revert_all()
    _print_results(results)
    print("\nSnapshot deleted.")


def cmd_reset(args: argparse.Namespace) -> None:
    _require_admin()

    only = getattr(args, "only", None) or None

    if getattr(args, "config", None):
        # User provided a yaml — use it as the action scope
        profile = load_profile(Path(args.config))
        controller = OsConfigController(profile=profile)
        print("\nResetting OS configuration to Windows defaults …\n")
        if only:
            print(f"  (filtering to: {', '.join(only)})\n")
        results = controller.reset_all(only=only)
        _print_results(results)
    else:
        # No yaml: build a full profile but exclude the credential-requiring
        # auto_admin_logon field, then handle AutoAdminLogonAction separately.
        from dataclasses import replace as _dc_replace
        profile = _dc_replace(OsConfigProfile.default(), enable_auto_admin_logon=False)
        controller = OsConfigController(profile=profile)

        print("\nResetting OS configuration to Windows defaults …\n")
        if only:
            print(f"  (filtering to: {', '.join(only)})\n")

        results = controller.reset_all(only=only)

        # Handle AutoAdminLogonAction separately (no credentials required for reset)
        auto_logon_name = AutoAdminLogonAction.name
        if only is None or auto_logon_name in only:
            try:
                AutoAdminLogonAction().restore_os_default()
                results[auto_logon_name] = "reset"
            except Exception as exc:
                results[auto_logon_name] = f"error:{exc}"

        _print_results(results)

    print("\nDone. No snapshot was modified.")


def cmd_status(args: argparse.Namespace) -> None:
    profile = _load_profile(args)
    snapshot_path = Path(args.snapshot) if getattr(args, "snapshot", None) else _DEFAULT_SNAPSHOT
    state_manager = OsConfigStateManager(path=snapshot_path)
    controller = OsConfigController(profile=profile, state_manager=state_manager)

    print("\nCurrent OS configuration status\n")
    print(f"  {'Action':<40} {'In target state?'}")
    print(f"  {'-'*40} {'-'*16}")

    check_results = controller.check_all()
    for name, ok in check_results.items():
        if ok is None:
            symbol = "~  unsupported"
        elif ok:
            symbol = "✓  yes (already applied)"
        else:
            symbol = "✗  no  (apply needed)"
        print(f"  {name:<40} {symbol}")

    snapshot_exists = state_manager.exists()
    print(f"\n  Snapshot file: {'exists  → revert available' if snapshot_exists else 'not found'}")
    print(f"  Snapshot path: {snapshot_path}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="osconfig_tool",
        description="Apply / revert / reset OS configuration settings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python osconfig_tool.py apply --config osconfig.yaml
  python osconfig_tool.py revert
  python osconfig_tool.py reset
  python osconfig_tool.py reset --only DefenderAction FirewallAction
  python osconfig_tool.py status --config osconfig.yaml
  python osconfig_tool.py apply --default
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── apply ────────────────────────────────────────────────────────────
    p_apply = sub.add_parser("apply", help="Apply settings and save snapshot")
    _add_config_args(p_apply)
    p_apply.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing snapshot without prompting",
    )
    _add_snapshot_arg(p_apply)

    # ── revert ───────────────────────────────────────────────────────────
    p_revert = sub.add_parser("revert", help="Revert to pre-apply snapshot")
    p_revert.add_argument(
        "--config",
        metavar="PATH",
        help="Optional yaml (helps build the correct action list for revert)",
    )
    _add_snapshot_arg(p_revert)

    # ── reset ────────────────────────────────────────────────────────────
    p_reset = sub.add_parser("reset", help="Reset settings to Windows out-of-box defaults")
    p_reset.add_argument(
        "--config",
        metavar="PATH",
        help="Optional yaml to limit which actions are considered",
    )
    p_reset.add_argument(
        "--only",
        nargs="+",
        metavar="ACTION",
        help="Only reset specific actions (e.g. DefenderAction FirewallAction)",
    )

    # ── status ───────────────────────────────────────────────────────────
    p_status = sub.add_parser("status", help="Show current state vs target profile")
    _add_config_args(p_status)
    _add_snapshot_arg(p_status)

    return parser


def _add_config_args(p: argparse.ArgumentParser) -> None:
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--config",
        metavar="PATH",
        help="Path to osconfig.yaml (default: auto-discover osconfig.yaml next to this script)",
    )
    group.add_argument(
        "--default",
        dest="default_profile",
        action="store_true",
        help="Use OsConfigProfile.default() (all settings enabled)",
    )


def _add_snapshot_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--snapshot",
        metavar="PATH",
        help=f"Snapshot file path (default: {_DEFAULT_SNAPSHOT})",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "apply":  cmd_apply,
        "revert": cmd_revert,
        "reset":  cmd_reset,
        "status": cmd_status,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
