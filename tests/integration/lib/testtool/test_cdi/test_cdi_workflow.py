"""
CDI Controller Integration Tests

These tests exercise CDIController against a REAL running DiskInfo64.exe
on a real Windows machine.  They are intentionally NOT mocked — every test
here opens the application, interacts with its GUI, and checks that the
produced files exist and contain valid content.

Requirements
------------
- DiskInfo64.exe present (configure via CDI_EXE_PATH or default path)
- At least one physical disk visible to CrystalDiskInfo
- pywinauto installed
- A desktop / display environment (for GUI automation)
- Run as Administrator (DiskInfo64 requires raw-disk access)

Environment-variable overrides
-------------------------------
CDI_EXE_PATH       path to DiskInfo64.exe
CDI_LOG_DIR        base directory for output files
CDI_DRIVE_LETTER   drive letter to capture screenshot for (e.g. C:)
CDI_TIMEOUT        per-test timeout in seconds (default 120)

Run only integration tests
--------------------------
    pytest tests/integration/lib/testtool/test_cdi/ -v -m "integration"

Skip integration tests
----------------------
    pytest ... -m "not integration"
"""

import json
import sys
import time
from pathlib import Path

import pytest

# ---- project root on sys.path ----
_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.testtool.cdi import CDIController
from lib.testtool.cdi.exceptions import CDIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_controller(cdi_env, log_dir, prefix='', **extra) -> CDIController:
    """Build a CDIController pointed at a given log directory."""
    return CDIController(
        executable_path=cdi_env['executable_path'],
        log_path=str(log_dir),
        log_prefix=prefix,
        screenshot_drive_letter=cdi_env['drive_letter'],
        timeout_seconds=cdi_env['timeout'],
        **extra,
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_cdi
@pytest.mark.slow
class TestCDIControllerIntegration:
    """End-to-end CDI controller tests against real DiskInfo64.exe."""

    # ------------------------------------------------------------------
    # T01 – Full workflow produces expected output files
    # ------------------------------------------------------------------

    @pytest.mark.timeout(180)
    def test_full_workflow_creates_txt(self, cdi_env, check_environment, clean_log_dir):
        """
        Full workflow must create DiskInfo.txt in the log directory.

        This is the most fundamental check — if the txt file is missing,
        every downstream step (parse → JSON, screenshots) cannot work.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        txt = clean_log_dir / "DiskInfo.txt"
        assert txt.exists(), (
            f"DiskInfo.txt not found in {clean_log_dir}.  "
            f"controller.status={controller.status}"
        )

    @pytest.mark.timeout(180)
    def test_full_workflow_creates_json(self, cdi_env, check_environment, clean_log_dir):
        """
        Full workflow must create a valid DiskInfo.json.

        The JSON file is the parsed output used by all SMART comparison helpers.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        json_path = clean_log_dir / "DiskInfo.json"
        assert json_path.exists(), (
            f"DiskInfo.json not found in {clean_log_dir}.  "
            f"controller.status={controller.status}"
        )

        with open(json_path) as f:
            data = json.load(f)

        assert 'disks' in data, "DiskInfo.json missing 'disks' key"
        assert len(data['disks']) >= 1, "DiskInfo.json contains no disk entries"

    @pytest.mark.timeout(180)
    def test_full_workflow_controller_status_true(self, cdi_env, check_environment, clean_log_dir):
        """
        CDIController.status must be True after a successful run.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        assert controller.status is True, (
            f"Expected controller.status=True, got {controller.status!r}"
        )

    @pytest.mark.timeout(180)
    def test_full_workflow_json_has_cdi_version(self, cdi_env, check_environment, clean_log_dir):
        """
        Parsed JSON must contain the CrystalDiskInfo version string.
        Confirms the text log was generated (not empty) and parsed correctly.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        json_path = clean_log_dir / "DiskInfo.json"
        assert json_path.exists(), (
            f"DiskInfo.json not found.  controller.status={controller.status}"
        )

        with open(json_path) as f:
            data = json.load(f)

        assert 'CDI' in data, "JSON missing 'CDI' section"
        assert 'version' in data['CDI'], "JSON missing CDI version"
        assert data['CDI']['version'], "CDI version is empty"

    # ------------------------------------------------------------------
    # T02 – Log prefix is applied to output filenames
    # ------------------------------------------------------------------

    @pytest.mark.timeout(180)
    def test_log_prefix_applied(self, cdi_env, check_environment, clean_log_dir):
        """
        When log_prefix='Before_', all output files must start with 'Before_'.
        """
        controller = _make_controller(cdi_env, clean_log_dir, prefix='Before_')
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        assert (clean_log_dir / "Before_DiskInfo.txt").exists(), (
            "Before_DiskInfo.txt not found"
        )
        assert (clean_log_dir / "Before_DiskInfo.json").exists(), (
            "Before_DiskInfo.json not found"
        )

    # ------------------------------------------------------------------
    # T03 – JSON structure (disks have expected fields)
    # ------------------------------------------------------------------

    @pytest.mark.timeout(180)
    def test_json_disk_has_model(self, cdi_env, check_environment, clean_log_dir):
        """
        Each disk entry in the parsed JSON must have at least a 'Model' field.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        with open(clean_log_dir / "DiskInfo.json") as f:
            data = json.load(f)

        for disk in data['disks']:
            assert 'Model' in disk, f"Disk entry missing 'Model': {disk}"

    @pytest.mark.timeout(180)
    def test_json_disk_has_smart(self, cdi_env, check_environment, clean_log_dir):
        """
        Each disk entry must have a non-empty 'S.M.A.R.T.' list.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        with open(clean_log_dir / "DiskInfo.json") as f:
            data = json.load(f)

        for disk in data['disks']:
            assert 'S.M.A.R.T.' in disk, f"Disk '{disk.get('Model')}' missing S.M.A.R.T. data"
            assert len(disk['S.M.A.R.T.']) >= 1, (
                f"Disk '{disk.get('Model')}' has empty S.M.A.R.T. list"
            )

    # ------------------------------------------------------------------
    # T04 – get_drive_info helper
    # ------------------------------------------------------------------

    @pytest.mark.timeout(180)
    def test_get_drive_info_returns_model(self, cdi_env, check_environment, clean_log_dir):
        """
        get_drive_info() must return a non-empty 'Model' for the target drive.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        assert controller.status is True
        drive = cdi_env['drive_letter']
        model = controller.get_drive_info(drive, '', 'Model')
        assert model, f"Model is empty for drive {drive}"
        print(f"\nDrive {drive} model: {model}")

    # ------------------------------------------------------------------
    # T05 – get_smart_value helper
    # ------------------------------------------------------------------

    @pytest.mark.timeout(180)
    def test_get_smart_value_returns_int(self, cdi_env, check_environment, clean_log_dir):
        """
        get_smart_value() must return a list with at least one dict whose
        values are non-negative integers.
        """
        controller = _make_controller(cdi_env, clean_log_dir)
        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        assert controller.status is True

        # Read all SMART attributes and find the first one that exists
        json_path = clean_log_dir / "DiskInfo.json"
        with open(json_path) as f:
            data = json.load(f)
        drive = cdi_env['drive_letter']
        disks = [d for d in data['disks'] if drive in d.get('Drive Letter', '')]
        if not disks:
            pytest.skip(f"Drive {drive} not found in DiskInfo.json")

        smart_attrs = [s['Attribute Name'] for s in disks[0].get('S.M.A.R.T.', [])]
        if not smart_attrs:
            pytest.skip("No SMART attributes found for drive")

        attr_name = smart_attrs[0]
        values = controller.get_smart_value(drive, '', [attr_name])
        assert isinstance(values, list) and len(values) == 1
        assert attr_name in values[0]
        assert isinstance(values[0][attr_name], int)
        assert values[0][attr_name] >= 0
        print(f"\nSMART '{attr_name}' = {values[0][attr_name]}")

    # ------------------------------------------------------------------
    # T06 – Two-snapshot no-increase comparison
    # ------------------------------------------------------------------

    @pytest.mark.timeout(360)
    def test_smart_no_increase_between_snapshots(
        self, cdi_env, check_environment, clean_log_dir
    ):
        """
        Run CDI twice (Before_ and After_ snapshots) without any disk
        activity between them.  Attributes like 'Unsafe Shutdowns' must
        not increase.

        Note: 'Power On Hours' may increment by 1 over time so we use
        a safer attribute.  The test auto-selects the first attribute
        whose before and after raw values are equal.
        """
        drive = cdi_env['drive_letter']

        # -- Before snapshot --
        before_ctrl = _make_controller(cdi_env, clean_log_dir, prefix='Before_')
        before_ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
        before_ctrl.start()
        before_ctrl.join(timeout=cdi_env['timeout'] + 30)
        assert before_ctrl.status is True, "Before snapshot failed"

        # -- After snapshot --
        after_ctrl = _make_controller(cdi_env, clean_log_dir, prefix='After_')
        after_ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
        after_ctrl.start()
        after_ctrl.join(timeout=cdi_env['timeout'] + 30)
        assert after_ctrl.status is True, "After snapshot failed"

        # Find a stable attribute (same before & after) to assert on
        json_before = clean_log_dir / "Before_DiskInfo.json"
        with open(json_before) as f:
            data_before = json.load(f)

        disks = [d for d in data_before['disks'] if drive in d.get('Drive Letter', '')]
        if not disks:
            pytest.skip(f"Drive {drive} not found")

        smart_before = {
            s['Attribute Name']: int(s['RawValues'], 16)
            for s in disks[0].get('S.M.A.R.T.', [])
        }

        json_after = clean_log_dir / "After_DiskInfo.json"
        with open(json_after) as f:
            data_after = json.load(f)

        disks_after = [d for d in data_after['disks'] if drive in d.get('Drive Letter', '')]
        if not disks_after:
            pytest.skip(f"Drive {drive} not found in after snapshot")

        smart_after = {
            s['Attribute Name']: int(s['RawValues'], 16)
            for s in disks_after[0].get('S.M.A.R.T.', [])
        }

        # Pick attributes whose value stayed exactly the same
        stable = [k for k in smart_before if smart_before[k] == smart_after.get(k)]
        if not stable:
            pytest.skip(
                "All SMART attributes changed between snapshots — "
                "cannot perform no-increase check in this environment"
            )

        attr = stable[0]
        ok, msg = after_ctrl.compare_smart_value_no_increase(
            drive, 'Before_', 'After_', [attr]
        )
        assert ok, msg
        print(f"\nNo-increase check passed for '{attr}': {smart_before[attr]} == {smart_after[attr]}")

    # ------------------------------------------------------------------
    # T07 – CDIController does not block indefinitely on bad exe path
    # ------------------------------------------------------------------

    @pytest.mark.timeout(30)
    def test_bad_exe_path_sets_status_false(self, cdi_env, clean_log_dir):
        """
        When executable_path points to a nonexistent binary, the controller
        must set status=False (not hang forever).
        """
        ctrl = CDIController(
            executable_path='./nonexistent/DiskInfo64.exe',
            log_path=str(clean_log_dir),
            timeout_seconds=10,
        )
        ctrl.start()
        ctrl.join(timeout=20)
        assert ctrl.status is False, (
            f"Expected status=False for missing exe, got {ctrl.status!r}"
        )

    # ------------------------------------------------------------------
    # T08 – Load configuration from Config.json
    # ------------------------------------------------------------------

    @pytest.mark.timeout(180)
    def test_workflow_from_config_json(self, cdi_env, check_environment, clean_log_dir, test_root):
        """
        CDIController.load_config_from_json() must correctly map the
        legacy Config.json keys (ExePath, LogPath, …) to CDIConfig keys,
        and the full workflow must succeed.

        Uses the centralized integration test Config.json at
        tests/integration/Config/Config.json, overriding the ExePath to
        point at the shared unit-test binary so the test is self-contained.
        """
        config_path = test_root / "integration" / "Config" / "Config.json"
        if not config_path.exists():
            pytest.skip(f"Config.json not found at {config_path}")

        # Build controller with no positional args first
        controller = CDIController()

        # Load from Config.json (legacy key names)
        controller.load_config_from_json(str(config_path), config_key='cdi')

        # Override exe path and log dir to match the test environment
        controller.set_config(
            executable_path=cdi_env['executable_path'],
            log_path=str(clean_log_dir),
            timeout_seconds=cdi_env['timeout'],
        )

        print(f"\nexecutable_path : {controller._config['executable_path']}")
        print(f"log_path        : {controller._config['log_path']}")
        print(f"log_prefix      : {controller._config['log_prefix']}")
        print(f"drive_letter    : {controller._config['screenshot_drive_letter']}")

        controller.start()
        controller.join(timeout=cdi_env['timeout'] + 30)

        assert controller.status is True, (
            f"Workflow failed after loading Config.json. status={controller.status!r}"
        )
        assert (clean_log_dir / "DiskInfo.json").exists(), "DiskInfo.json not created"
