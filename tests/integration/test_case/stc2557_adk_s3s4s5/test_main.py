"""
STC-2557: ADK S3/S4/S5 Power State Performance Test

Step-based end-to-end test for running a WAC multi-assessment job covering
Standby Performance (S3), Hibernate Performance (S4), and Boot Performance
Full Boot (S5) as a single Configure Job with one click_start.

Survives the OS-level hibernate and cold reboot that WAC triggers for S4 and
S5 using RebootManager to persist state and auto-restart pytest.

Workflow:
    Step 1  — Precondition: kill wac/axe, clear logs, remove stale reboot state.
    Step 2  — Install Tools: install Windows ADK and dependencies via Chocolatey.
    Step 3  — Apply OsConfig: configure Task Scheduler entries (SystemRestore,
              MemoryDiagnostic, McAfee).
    Step 4  — Clean Environment: remove stale WAC result/job/test dirs then
              reboot the DUT for a clean platform environment; startup BAT
              resumes pytest at step 6.
    Step 5  — CDI Before: capture SMART baseline (Before_ prefix).
    Step 6  — Configure BPFS: open WAC Configure Job, add Boot Performance
              Fast Startup, leave on Configure Job page.
    Step 7  — Configure S5 (BPFB): connect WAC, add Boot Performance Full Boot,
              leave on Configure Job page.
    Step 8  — Configure S3: connect WAC, add Standby Performance,
              configure params, leave on Configure Job page.
    Step 9  — Configure S4: connect WAC, add Hibernate Performance, configure
              params, leave on Configure Job page.
    Step 10 — Start Job: connect WAC, submit Configure Job, save custom job,
              connect Assessment Launcher, persist reboot state,
              click Start (single, unique start point).
              WAC runs sequentially:
                BPFS — Fast Startup hibernate/resume  — pytest process survives.
                S3   — Standby sleep/wake             — pytest process survives.
                S4   — Hibernate          — OS session terminates; startup BAT
                                            resumes pytest at step 11 (Run #3).
                S5   — Cold reboot        — OS session terminates again; startup
                                            BAT resumes pytest at step 11 (Run #4).
    Step 11 — Wait Results: connect WAC, wait for View Results page (timeout
              covers the full four-assessment run including S5 BPFB).
    Step 12 — Verify: assert no errors, assert result directory and AxeLog.txt
              exist.
    Step 13 — CDI After: capture post-assessment SMART snapshot (After_ prefix).
    Step 14 — SMART Compare: verify no unsafe shutdown increase and error
              counters are zero.

Requirements:
    - Windows ADK (wac.exe) must be installed via Chocolatey.
    - Must run as Administrator on Windows build 22000 / 22621 / 26100.
    - Hibernation must be enabled: `powercfg /h on`
    - BIOS must support wake timers for S3 (or use Modern Standby fallback).

Environment variables:
    ADK_JOB_NAME    Job name in the Save Custom Job dialog
                    (default: S3S4S5_Workflow_Test)
    ADK_JOB_TIMEOUT Max seconds to wait for the full job View Results
                    (default: 14400 — 4 hours)
    ADK_LOG_DIR     Override the base directory for log output

Run:
    pytest tests/integration/test_case/stc2557_adk_s3s4s5/test_main.py -v -s
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from lib.logger import get_module_logger, clear_log_files
from lib.testtool.tool_installer import ToolInstaller
from lib.testtool.windows_adk import ADKController
from lib.testtool.windows_adk.config import WAC_EXE, get_build_number
from lib.testtool.windows_adk.result_reader import WACRunResult
from lib.testtool.windows_adk.version_adapter import VersionAdapter
from lib.testtool.osconfig import OsConfigController
from lib.testtool.osconfig.state_manager import OsConfigStateManager
from lib.testtool.osconfig.profile_loader import load_profile
from lib.testtool.cdi import CDIController

logger = get_module_logger(__name__)


@pytest.mark.integration
@pytest.mark.requires_windows_adk
@pytest.mark.slow
class TestSTC2557ADKS3S4S5(BaseTestCase):
    """
    STC-2557: ADK S3/S4/S5 power state assessment — reboot-survivable.

    Runs Standby Performance (S3), Hibernate Performance (S4), and Boot
    Performance Full Boot (S5) as a single WAC Configure Job.  The three
    assessments are configured across steps 6–9 and started in step 10 with
    a single click_start.  RebootManager handles state persistence across the
    S4 hibernate and S5 cold reboot.
    """

    # Class-level state: populated by test_11, consumed by test_12
    _wac_result: "WACRunResult | None" = None

    # Comment: steps 6-9 configure BPFS + S3/S4/S5 in one Configure Job;
    #          step 10 starts all four assessments with a single click_start.
    _osconfig_controller: "OsConfigController | None" = None

    # ------------------------------------------------------------------
    # Class-level fixture — overrides BaseTestCase.setup_teardown_class
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request, testcase_config, runcard_params):
        """Initialise working directory, VersionAdapter, RebootManager, and RunCard."""
        cls = request.cls
        cls.original_cwd = os.getcwd()

        test_dir = cls._setup_working_directory(__file__)

        # ── Config ────────────────────────────────────────────────────────────
        cls.config = testcase_config.tool_config

        # Resolve log path: ADK_LOG_DIR env var or test directory
        base = os.getenv("ADK_LOG_DIR")
        cls.log_path = (
            str(Path(base) / "s3s4s5") if base
            else str(test_dir / "testlog" / "s3s4s5")
        )
        Path(cls.log_path).mkdir(parents=True, exist_ok=True)

        cls.adapter = VersionAdapter(get_build_number())
        cls.reboot_mgr = RebootManager(
            total_tests=cls._count_test_methods(),
            auto_login_config=cls.config.get('osconfig', {}),
        )

        phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        _tools_yaml = Path(__file__).parent / "Config" / "tools.yaml"
        ToolInstaller(_tools_yaml).install_pre_runcard()
        logger.info(f"[SETUP] SMICLI_PATH (after install) : {os.environ.get('SMICLI_PATH', 'NOT SET')}")
        smicli_exe = os.environ.get('SMICLI_PATH', '')
        logger.info(f"[SETUP] SmiCli2.exe exists: {Path(smicli_exe).exists() if smicli_exe else False}")
        # ── RunCard ─────────────────────────────────────────────────────────
        if not cls.reboot_mgr.is_recovering():
            cls._init_runcard(runcard_params)
        else:
            cls.runcard = None

        yield

        cls._teardown_runcard(request.session)

        cls._revert_osconfig(
            Path(__file__).parent / "Config" / "osconfig.yaml",
            cls._osconfig_controller,
            logger,
        )

        cls._teardown_reboot_manager()
        logger.info(f"{cls.__name__} session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Step 1 — Precondition
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition")
    def test_01_precondition(self):
        """Kill wac/axe, clear logs, and remove stale reboot state."""
        for proc in ("wac.exe", "axe.exe"):
            subprocess.run(["taskkill", "/f", "/im", proc], capture_output=True)
        time.sleep(1)

        # Clean entire testlog directory so previous run artefacts don't accumulate.
        self._cleanup_testlog_directory()

        clear_log_files()
        Path(self.log_path).mkdir(parents=True, exist_ok=True)

        # Remove stale reboot state so a re-run always starts fresh.
        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            self.reboot_mgr.state = self.reboot_mgr._load_state()
            logger.info(f"[TEST_01] Removed stale reboot state: {state_file}")

    # ------------------------------------------------------------------
    # Step 2 — Install Tools
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, "Install tools")
    def test_02_install_tools(self):
        """Install tools declared in Config/tools.yaml (windows-adk, reinstall=true)."""
        _tools_yaml = Path(__file__).parent / "Config" / "tools.yaml"
        ToolInstaller(_tools_yaml).install_all()
        logger.info("[TEST_02] Tools installed")

    # ------------------------------------------------------------------
    # Step 3 — Apply OS Configuration
    # ------------------------------------------------------------------

    @pytest.mark.order(3)
    @step(3, "Apply OS configuration")
    def test_03_apply_osconfig(self):
        """Apply OS configuration (Task Scheduler prep: SystemRestore, MemoryDiagnostic, McAfee)."""
        _osconfig_yaml = Path(__file__).parent / "Config" / "osconfig.yaml"
        profile = load_profile(_osconfig_yaml)
        controller = OsConfigController(
            profile=profile,
            state_manager=OsConfigStateManager(),
        )
        controller.apply_all()
        TestSTC2557ADKS3S4S5._osconfig_controller = controller
        logger.info("[TEST_03] OsConfig applied successfully")

    # ------------------------------------------------------------------
    # Step 4 — Clean Environment
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Clean Environment")
    def test_04_clean_environment(self):
        """
        Remove stale WAC result, job, and test directories, then reboot the DUT
        to flush residual background processes and apply any pending OS/driver
        changes introduced by steps 2–3.

        RebootManager persists state, writes the startup BAT, issues
        shutdown /r, and calls os._exit(0).  pytest resumes at
        test_06_configure_bpfs after the system comes back up (Run #2).
        """
        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl.cleanup_dirs()
        logger.info("[TEST_04] WAC directories cleaned")

        logger.info("[TEST_04] Issuing reboot for clean platform environment...")
        self.reboot_mgr.setup_reboot(
            delay=10,
            reason="test_04_clean_environment: clean platform environment before WAC assessment",
            test_file=__file__,
        )

    # ------------------------------------------------------------------
    # Step 5 — CDI Before
    # ------------------------------------------------------------------

    @pytest.mark.order(5)
    @step(5, "CDI Before — SMART baseline")
    def test_05_cdi_before(self):
        """Run CrystalDiskInfo to capture SMART baseline (Before_ prefix)."""
        cfg = self.config['cdi']
        ctrl = CDIController(
            executable_path=cfg['ExePath'],
            log_path=cfg['LogPath'],
            log_prefix='Before_',
            screenshot_drive_letter=cfg.get('ScreenShotDriveLetter', 'C:'),
        )
        ctrl.start()
        ctrl.join(timeout=180)
        if not ctrl.status:
            pytest.fail(f"CDI Before failed (status={ctrl.status})")
        logger.info("[TEST_05] CDI Before complete")

    # ------------------------------------------------------------------
    # Step 6 — Configure BPFS (Boot Performance Fast Startup)
    # ------------------------------------------------------------------

    @pytest.mark.order(6)
    @step(6, "Configure BPFS — Boot Performance Fast Startup")
    def test_06_configure_bpfs(self):
        """Open WAC Configure Job page and add Boot Performance Fast Startup (no Run)."""
        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl._ui.open(WAC_EXE)
        ctrl._ui.add_bpfs_to_configure_job(num_iters=1)
        logger.info("[TEST_06] BPFS added — WAC on Configure Job page")

    # ------------------------------------------------------------------
    # Step 7 — Configure S5 (BPFB)
    # ------------------------------------------------------------------

    @pytest.mark.order(7)
    @step(7, "Configure S5 — BPFB")
    def test_07_configure_s5(self):
        """Connect WAC Configure Job page and add BPFB (no submit yet)."""
        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl._ui.connect()
        ctrl._ui.add_bpfb_to_configure_job(num_iters=1)
        logger.info("[TEST_07] BPFB added — WAC on Configure Job page")

    # ------------------------------------------------------------------
    # Step 8 — Configure S3 (Standby Performance)
    # ------------------------------------------------------------------

    @pytest.mark.order(8)
    @step(8, "Configure S3 — Standby Performance")
    def test_08_configure_s3(self):
        """Connect WAC Configure Job page and add Standby Performance (no Run)."""
        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl._ui.connect()
        ctrl._ui.add_standby_to_configure_job(num_iters=1)
        logger.info("[TEST_08] Standby Performance added — WAC on Configure Job page")

    # ------------------------------------------------------------------
    # Step 9 — Configure S4 (Hibernate Performance)
    # ------------------------------------------------------------------

    @pytest.mark.order(9)
    @step(9, "Configure S4 — Hibernate Performance")
    def test_09_configure_s4(self):
        """Connect to WAC Configure Job page and add Hibernate Performance."""
        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl._ui.connect()
        ctrl._ui.add_hibernate_to_configure_job(num_iters=1)
        logger.info("[TEST_09] Hibernate Performance added — WAC on Configure Job page")

    # ------------------------------------------------------------------
    # Step 10 — Persist reboot state and click Start (single start point)
    # ------------------------------------------------------------------

    @pytest.mark.order(10)
    @step(10, "Start Job — BPFS → S3 → S4 → S5")
    def test_10_start_job(self):
        """
        Submit the four-assessment Configure Job, save it as a custom job,
        persist reboot state, then click Start (the single, unique start point).

        WAC runs the four assessments sequentially:
          BPFS — Fast Startup hibernate/resume: pytest process survives in RAM.
          S3   — Standby sleep/wake: pytest process survives in RAM.
          S4   — Hibernate: OS session terminates; startup BAT resumes
                 pytest at test_11 after the hibernate resume (Run #3).
          S5   — Cold reboot: OS session terminates (WAC Launcher triggers);
                 startup BAT resumes pytest at test_11 after boot (Run #4).
        """
        job_name = os.getenv("ADK_JOB_NAME", "S3S4S5_Workflow_Test")
        ctrl = ADKController(config={"log_path": self.log_path})
        # Connect to Configure Job page (left open by test_09), submit, save, open launcher.
        ctrl._ui.connect()
        ctrl._ui.submit_configure_job()
        ctrl._ui.save_custom_job(job_name)
        ctrl._ui.connect_launcher()

        # Persist state and write the startup BAT BEFORE clicking Start.
        # The earliest OS-level session termination is S4 hibernate.
        self.reboot_mgr.prepare_for_external_reboot(
            step_name="test_10_start_job",
            test_file=__file__,
        )

        logger.info("[TEST_10] Clicking Start — WAC will run BPFS → S3 → S4 → S5 sequentially")
        ctrl._ui.click_start()

        # Wall-clock guard:
        #   BPFS/S3 — pytest process survives, sleep(120) completes normally.
        #   S4 hibernate  — OS terminates this process mid-sleep; the startup BAT
        #                   will relaunch pytest after resume.
        _t_click = time.time()
        time.sleep(120)
        _wall = time.time() - _t_click
        if _wall > 300:
            logger.info(
                "[TEST_10] Reboot detected (wall time=%.0fs) — "
                "exiting so startup BAT handles test_11+", _wall
            )
            os._exit(0)

    # ------------------------------------------------------------------
    # Step 11 — Wait for View Results (resumes after S5 cold reboot)
    # ------------------------------------------------------------------

    @pytest.mark.order(11)
    @step(11, "Wait for WAC View Results")
    def test_11_wait_results(self):
        """
        Connect to WAC and wait for the entire four-assessment job to
        complete and show the View Results page.

        This step runs in Run #3 (after S4 resume) while WAC Launcher
        continues running S5.  If S5 cold reboot interrupts this step
        before mark_completed, the startup BAT retries it in Run #4 —
        that is the expected behaviour.

        Pass criteria: errors == 0.
        """
        timeout = int(os.getenv("ADK_JOB_TIMEOUT", "14400"))
        ctrl = ADKController(config={"log_path": self.log_path})

        wac_result = ctrl._ui.read_view_results(
            timeout=timeout,
            debug_enumerate=True,   # log UI element IDs on first run
        )

        logger.info(
            "[TEST_11] errors=%d  warnings=%d  analysis_complete=%s",
            wac_result.errors, wac_result.warnings, wac_result.analysis_complete,
        )
        logger.info("[TEST_11] machine     : %s", wac_result.machine_name)
        logger.info("[TEST_11] run_time    : %s", wac_result.run_time)
        logger.info("[TEST_11] result_path : %s", wac_result.result_path)

        # Store for step 12 verification.
        TestSTC2557ADKS3S4S5._wac_result = wac_result

        assert wac_result.errors == 0, (
            f"WAC multi-assessment job completed with {wac_result.errors} error(s). "
            f"Results path: {wac_result.result_path}"
        )

    # ------------------------------------------------------------------
    # Step 12 — Verify result artefacts
    # ------------------------------------------------------------------

    @pytest.mark.order(12)
    @step(12, "Verify result artefacts")
    def test_12_verify(self):
        """Assert the result directory and AxeLog.txt exist."""
        wac_result = getattr(TestSTC2557ADKS3S4S5, "_wac_result", None)

        assert wac_result is not None, (
            "test_11_wait_results did not store a WACRunResult — "
            "ensure test_11 ran and passed before test_12."
        )
        assert wac_result.result_path, (
            f"WAC did not report a Results path. "
            f"errors={wac_result.errors}  warnings={wac_result.warnings}\n"
            "Check log for [ViewResults DEBUG] entries to diagnose."
        )

        result_dir = Path(wac_result.result_path)
        assert result_dir.is_dir(), (
            f"WAC Results directory does not exist: {result_dir}"
        )

        # WAC multi-assessment job: outermost AxeLog.txt covers the full job.
        axelog = result_dir / "AxeLog.txt"
        assert axelog.exists(), f"AxeLog.txt not found in {result_dir}"
        logger.info(f"[TEST_12] AxeLog.txt verified: {axelog}")

        # ── (1) Create windows_adk collection directory under testlog ─────────
        adk_dir = Path(self.log_path).parent / "windows_adk"
        adk_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[TEST_12] Collection dir: {adk_dir}")

        # ── (2) Zip the WAC result directory into windows_adk ─────────────────
        zip_base = adk_dir / result_dir.name
        shutil.make_archive(str(zip_base), "zip", str(result_dir.parent), result_dir.name)
        logger.info(f"[TEST_12] Results archived: {zip_base}.zip")

        # ── (3) Screenshot of the WAC result window ───────────────────────────
        job_name = os.getenv("ADK_JOB_NAME", "S3S4S5_Workflow_Test")
        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl._ui.take_screenshot(str(adk_dir), result_dir.name, tab_title=job_name)

        logger.info(
            "[TEST_12] Summary — errors=%d  warnings=%d  result_path=%s",
            wac_result.errors, wac_result.warnings, wac_result.result_path,
        )

    # ------------------------------------------------------------------
    # Step 13 — CDI After
    # ------------------------------------------------------------------

    @pytest.mark.order(13)
    @step(13, "CDI After — SMART snapshot")
    def test_13_cdi_after(self):
        """Run CrystalDiskInfo to capture post-assessment SMART data (After_ prefix)."""
        cfg = self.config['cdi']
        ctrl = CDIController(
            executable_path=cfg['ExePath'],
            log_path=cfg['LogPath'],
            log_prefix='After_',
            screenshot_drive_letter=cfg.get('ScreenShotDriveLetter', 'C:'),
        )
        ctrl.start()
        ctrl.join(timeout=180)
        if not ctrl.status:
            pytest.fail(f"CDI After failed (status={ctrl.status})")
        logger.info("[TEST_13] CDI After complete")

    # ------------------------------------------------------------------
    # Step 14 — SMART Compare
    # ------------------------------------------------------------------

    @pytest.mark.order(14)
    @step(14, "SMART Compare — verify drive health")
    def test_14_smart_compare(self):
        """
        Compare Before_ and After_ SMART snapshots:
        - Unsafe Shutdowns must NOT increase (indicates clean shutdown path)
        - Configured must-be-zero attributes must all be 0
        """
        cdi_cfg = self.config['cdi']
        smart_cfg = self.config.get('smart_check', {})
        drive = smart_cfg.get('drive_letter', cdi_cfg.get('ScreenShotDriveLetter', 'C:'))

        ctrl = CDIController(
            executable_path=cdi_cfg['ExePath'],
            log_path=cdi_cfg['LogPath'],
        )

        # ── Check: Unsafe Shutdowns must not increase ──────────────────────────
        no_increase_attrs = smart_cfg.get('no_increase_attributes', ['Unsafe Shutdowns'])
        ok, msg = ctrl.compare_smart_value_no_increase(
            drive_letter=drive,
            before_prefix='Before_',
            after_prefix='After_',
            keys=no_increase_attrs,
        )
        if not ok:
            pytest.fail(f"SMART no-increase check failed: {msg}")
        logger.info(f"[TEST_14] No-increase check passed: {no_increase_attrs}")

        # ── Check: error counters must be 0 ───────────────────────────────────
        zero_attrs = smart_cfg.get('must_be_zero_attributes', [])
        for attr in zero_attrs:
            ok, msg = ctrl.compare_smart_value(
                drive_letter=drive,
                log_prefix='After_',
                keys=[attr],
                expected_value=0,
            )
            if not ok:
                pytest.fail(f"SMART zero-check failed: {msg}")
            logger.info(f"[TEST_14] Zero-check passed: {attr}")

        logger.info("[TEST_14] All SMART checks passed")
