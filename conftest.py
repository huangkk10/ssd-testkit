"""
Root conftest.py — project-wide pytest hooks.

Hardware / real-device tests are skipped by default.
To run them, pass --run-hardware on the command line:

    pytest --run-hardware -m real_bat tests/unit/lib/testtool/test_smartcheck/
"""

import pytest
from pathlib import Path

try:
    import allure as _allure
    _ALLURE_AVAILABLE = True
except ImportError:
    _ALLURE_AVAILABLE = False

_REBOOT_STATE_FILENAME = "pytest_reboot_state.json"
# Captured once in pytest_configure; used by pytest_sessionfinish
_IS_POST_REBOOT_SESSION: bool = False


def _is_post_reboot_recovery() -> bool:
    """Search for any reboot state file under the project and return True if
    any of them has is_recovering=True.

    The state file is written relative to the test case directory (because
    _setup_working_directory changes cwd), so we cannot rely on a fixed path
    at the project root.  Instead we glob for the filename anywhere under the
    current working directory (the project root when pytest_configure runs).
    """
    import json
    # Check root-level first (fast path), then recurse into subdirectories
    candidates = list(Path(".").glob(f"**/{_REBOOT_STATE_FILENAME}"))
    for candidate in candidates:
        try:
            state = json.loads(candidate.read_text())
            if state.get("is_recovering", False):
                return True
        except Exception:
            continue
    return False


def pytest_configure(config: pytest.Config) -> None:
    """Clean allure-results only on a fresh run, not after a reboot recovery."""
    global _IS_POST_REBOOT_SESSION
    allure_dir = Path("allure-results")
    if _is_post_reboot_recovery():
        # Post-reboot Phase B: keep Phase A results so the report is complete
        _IS_POST_REBOOT_SESSION = True
        return
    if not allure_dir.exists():
        return
    # Fresh run: wipe previous results (equivalent to --clean-alluredir)
    import shutil
    shutil.rmtree(allure_dir, ignore_errors=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Clean up allure-results at the end of a post-reboot (Phase B) session.

    Does two things:
    1. Remove any SKIPPED results whose message contains "already completed"
       (written by BaseTestCase.setup_teardown_function when deselection fails).
    2. Deduplicate results with the same fullName — keeps the best-status /
       latest result and deletes stale copies left by previous failed runs.
       Priority: passed > failed > broken > skipped (then latest stop time).
    """
    if not _IS_POST_REBOOT_SESSION or not _ALLURE_AVAILABLE:
        return
    allure_dir = Path("allure-results")
    if not allure_dir.exists():
        return
    import json
    removed = 0

    # ── Pass 1: remove spurious "already completed" SKIP results ────────────
    for result_file in list(allure_dir.glob("*-result.json")):
        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if result.get("status") != "skipped":
            continue
        msg = str(result.get("statusDetails", {}).get("message", ""))
        if "already completed" in msg:
            result_file.unlink(missing_ok=True)
            removed += 1

    # ── Pass 2: deduplicate by fullName ──────────────────────────────────────
    # Collects all remaining result files, groups by fullName, and keeps only
    # the "best" one (PASS preferred; then latest stop timestamp as tiebreaker).
    _STATUS_RANK = {"passed": 0, "failed": 1, "broken": 2, "skipped": 3}
    by_name: dict = {}
    for result_file in allure_dir.glob("*-result.json"):
        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        full_name = result.get("fullName") or result.get("name", "")
        if not full_name:
            continue
        by_name.setdefault(full_name, []).append((result_file, result))

    for full_name, entries in by_name.items():
        if len(entries) <= 1:
            continue
        # Sort: best status first, then latest stop time first
        entries.sort(key=lambda x: (
            _STATUS_RANK.get(x[1].get("status", ""), 9),
            -x[1].get("stop", 0),
        ))
        # Keep entries[0], delete the rest
        for stale_file, _ in entries[1:]:
            stale_file.unlink(missing_ok=True)
            removed += 1

    if removed:
        print(f"\n[conftest] Cleaned {removed} duplicate/spurious result(s) "
              "from allure-results")


_HARDWARE_MARKS = {"real_bat", "real", "hardware"}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="Include tests marked real_bat / real / hardware (requires physical device).",
    )


def _expand_vscode_partial_selection(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """VS Code 'Debug Test' / 'Run Test' sends only the clicked test's node ID.

    For BaseTestCase subclasses that contain a reboot sequence this means
    test_01 … test_N-1 are missing and the prerequisite guard (require_after)
    fires immediately.  This hook detects partial class-level selection under
    VS Code and inserts the missing earlier tests so the full sequence runs.

    Only activates when the vscode_pytest plugin is loaded (-p vscode_pytest).
    Safe no-op for normal CLI runs.
    """
    if not config.pluginmanager.hasplugin("vscode_pytest"):
        return

    from collections import defaultdict

    # Group collected items by (file, class-name)
    by_class: dict = defaultdict(list)
    for item in items:
        if item.cls is not None:
            by_class[(str(item.fspath), item.cls.__name__)].append(item)

    extra: list[pytest.Item] = []
    for (fspath, cls_name), cls_items in by_class.items():
        cls = cls_items[0].cls
        # Only expand BaseTestCase subclasses (identified by the helper method)
        if not hasattr(cls, "_count_test_methods"):
            continue

        collected_names = {it.name for it in cls_items}

        # Ask the Module collector for every test it knows about
        module_collector = cls_items[0].getparent(pytest.Module)
        if module_collector is None:
            continue

        for sub_item in module_collector.collect():
            if (
                hasattr(sub_item, "cls")
                and sub_item.cls.__name__ == cls_name
                and sub_item.name not in collected_names
            ):
                extra.append(sub_item)

    if not extra:
        return

    # Prepend the missing items and re-sort the combined list by
    # @pytest.mark.order value (falling back to the method name).
    def _order_key(item: pytest.Item) -> tuple:
        marker = item.get_closest_marker("order")
        if marker and marker.args:
            try:
                return (int(marker.args[0]), item.name)
            except (ValueError, TypeError):
                pass
        return (9999, item.name)

    # Build per-class sorted lists, keeping non-class items in original position
    all_items = extra + [i for i in items]
    # Re-sort only within each class; items from different classes keep their
    # relative order by sorting stable on the class key first.
    class_order: dict = {}
    result: list[pytest.Item] = []
    seen_classes: set = set()
    plain: list[pytest.Item] = []

    for item in all_items:
        key = (str(item.fspath), item.cls.__name__) if item.cls else None
        if key and key in by_class:
            class_order.setdefault(key, []).append(item)
        else:
            plain.append(item)

    # Emit each class's tests in @order order, then plain items
    emitted_classes: set = set()
    for item in all_items:
        key = (str(item.fspath), item.cls.__name__) if item.cls else None
        if key and key in by_class and key not in emitted_classes:
            emitted_classes.add(key)
            result.extend(sorted(class_order[key], key=_order_key))
        elif key is None or key not in by_class:
            result.append(item)

    items[:] = result


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    # When VS Code "Debug Test" sends only a subset of tests from a reboot-
    # sequence class, expand the collection to include all class tests so
    # the prerequisite guards (require_after) are satisfied.
    _expand_vscode_partial_selection(config, items)

    # Deselect already-completed tests BEFORE the --run-hardware early return
    # so that Phase-B of a reboot cycle never generates a competing SKIPPED
    # result in Allure for tests that already PASSED in Phase A.
    if _is_post_reboot_recovery():
        import json
        completed: set[str] = set()
        for candidate in Path('.').glob(f'**/{_REBOOT_STATE_FILENAME}'):
            try:
                state = json.loads(candidate.read_text())
                completed.update(state.get('completed_tests', []))
            except Exception:
                pass
        if completed:
            keep = [item for item in items if item.name not in completed]
            # Do NOT call config.hook.pytest_deselected  allure-pytest
            # intercepts that hook and writes SKIPPED results, which would
            # overwrite the Phase-A PASSED results we want to preserve.
            items[:] = keep

    if config.getoption("--run-hardware"):
        return  # opt-in: run everything as requested

    skip = pytest.mark.skip(
        reason="Skipped by default (requires physical hardware). "
               "Pass --run-hardware to execute."
    )
    for item in items:
        item_marks = {m.name for m in item.iter_markers()}
        if item_marks & _HARDWARE_MARKS:
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Allure integration
# ---------------------------------------------------------------------------

_ALLURE_MARKER_MAP = {
    # Client dimension
    "client_lenovo":  ("tag",     "Client: Lenovo"),
    "client_hp":      ("tag",     "Client: HP"),
    "client_samsung": ("tag",     "Client: Samsung"),
    "client_micron":  ("tag",     "Client: Micron"),
    "client_asus":    ("tag",     "Client: ASUS"),
    "client_acer":    ("tag",     "Client: Acer"),
    # Interface dimension
    "interface_pcie": ("tag",     "Interface: PCIe"),
    "interface_sata": ("tag",     "Interface: SATA"),
    "interface_nvme": ("tag",     "Interface: NVMe"),
    # Project dimension
    "project_storagedv": ("epic", "StorageDV"),
    "project_ciq":       ("epic", "CIQ"),
    "project_standard":  ("epic", "Standard"),
    # Feature dimension
    "feature_burnin":         ("feature", "BurnIN Stress"),
    "feature_modern_standby": ("feature", "Modern Standby"),
    "feature_power":          ("feature", "Power Management"),
    "feature_storage":        ("feature", "Storage Stress"),
}


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store per-phase reports on the item so fixtures can read them."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """Map pytest markers to Allure Epic/Feature/Tag labels."""
    if _ALLURE_AVAILABLE:
        for marker in item.iter_markers():
            entry = _ALLURE_MARKER_MAP.get(marker.name)
            if entry is None:
                continue
            label_type, label_value = entry
            if label_type == "epic":
                _allure.dynamic.epic(label_value)
            elif label_type == "feature":
                _allure.dynamic.feature(label_value)
            else:
                _allure.dynamic.tag(label_value)
    yield


@pytest.fixture(autouse=True)
def attach_logs_on_failure(request):
    """Attach app.log / error.log to Allure report when a test fails."""
    yield
    if not _ALLURE_AVAILABLE:
        return
    rep = getattr(request.node, "rep_call", None)
    if rep is None or not rep.failed:
        return
    for log_name in ("app.log", "error.log"):
        log_path = Path("log") / log_name
        if log_path.exists():
            _allure.attach.file(
                str(log_path),
                name=log_name,
                attachment_type=_allure.attachment_type.TEXT,
            )
