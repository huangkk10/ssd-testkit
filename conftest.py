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
    allure_dir = Path("allure-results")
    if not allure_dir.exists():
        return
    if _is_post_reboot_recovery():
        # Post-reboot: keep Phase A results so the final report is complete
        return
    # Fresh run: wipe previous results (equivalent to --clean-alluredir)
    import shutil
    shutil.rmtree(allure_dir, ignore_errors=True)

_HARDWARE_MARKS = {"real_bat", "real", "hardware"}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="Include tests marked real_bat / real / hardware (requires physical device).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
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

    # Deselect already-completed tests during post-reboot recovery so that
    # allure-pytest does NOT generate a SKIPPED result that overwrites the
    # PASSED result written during the pre-reboot session.
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
            keep, deselect = [], []
            for item in items:
                (deselect if item.name in completed else keep).append(item)
            if deselect:
                config.hook.pytest_deselected(items=deselect)
                items[:] = keep


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
