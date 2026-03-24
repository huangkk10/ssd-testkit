"""
Boot Performance (Fast Startup) Configured-Job Workflow Integration Test

Step-based end-to-end test for running BPFS via the WAC Configure Job path.
Survives the system hibernate/reboot that WAC triggers as part of the
assessment, using RebootManager to persist state and auto-restart pytest.

Workflow:
    Step 1 — Precondition: clean up stale WAC directories (first boot only).
    Step 2 — Apply OS configuration (Search Index, OneDrive, Defender, etc.).
    Step 3 — Open WAC, configure BPFS (Iterations=1, wake timers ON), save
             custom job, connect launcher, persist reboot state, click Start.
             WAC will hibernate the machine immediately after Start is clicked.
    Step 4 — After reboot: connect to WAC, wait for the View Results page,
             read errors / warnings / result path.
    Step 5 — Assert final result artefacts exist.

Requirements:
    - Windows ADK (wac.exe) must be installed.
    - Must run as Administrator on a supported Windows build (22000/22621/26100).
    - Fast Startup must be enabled in Power settings.
    - Wake timers must be enabled (Group Policy / Power plan).

Environment variables:
    ADK_BPFS_JOB_NAME   Job name in the Save Custom Job dialog
                        (default: BPFS_Workflow_Test)
    ADK_BPFS_TIMEOUT    Max seconds to wait for the assessment result
                        (default: 7200 — 2 hours)
    ADK_LOG_DIR         Override the base directory for log output

    --- Mitigation flags (set to "0" to disable, default "1" = enabled) ---
    ADK_MITIGATIONS     Master switch for all mitigation measures below.
                        Set to "0" to run a bare baseline without any fixes.
    ADK_MIT_OSCONFIG    Step 2: apply OsConfig (disable Search/OneDrive/Defender etc.)
    ADK_MIT_FAST_STARTUP   Step 1: verify + auto-enable HiberbootEnabled registry key
    ADK_MIT_WAKE_TIMERS    Step 1: verify + auto-enable wake timers in active power plan
    ADK_MIT_SERVICES       Step 1: ensure SysMain / DiagTrack are running
    ADK_MIT_HIBERFIL       Step 1: refresh hibernate file (powercfg /hibernate off/on)

Run:
    pytest tests/integration/lib/testtool/test_windows_adk/test_bpfs_workflow.py -v -s
"""

import os
import subprocess
import sys
import time
import winreg
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.reboot_manager import RebootManager
from lib.logger import get_module_logger, clear_log_files
from lib.testtool.windows_adk import ADKController
from lib.testtool.windows_adk.config import WAC_EXE, get_build_number
from lib.testtool.windows_adk.result_reader import WACRunResult
from lib.testtool.windows_adk.version_adapter import VersionAdapter
from lib.testtool.osconfig import OsConfigController, OsConfigProfile, OsConfigStateManager

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# Mitigation feature flags — edit here to change defaults
#
# Set to True/False to enable/disable each mitigation.
# Environment variables (ADK_MITIGATIONS, ADK_MIT_*) override these defaults
# when set to "0" or "1".
# ---------------------------------------------------------------------------

_MITIGATIONS: dict[str, bool] = {
    # Master switch: set False to disable ALL mitigations at once.
    "ADK_MITIGATIONS":       False,

    # Step 1 mitigations
    "ADK_MIT_FAST_STARTUP":  False,   # Verify + auto-enable HiberbootEnabled registry key
    "ADK_MIT_WAKE_TIMERS":   False,   # Verify + auto-enable wake timers in active power plan
    "ADK_MIT_SERVICES":      False,   # Ensure SysMain / DiagTrack are running
    "ADK_MIT_HIBERFIL":      False,   # Refresh hibernate file (powercfg /hibernate off/on)

    # Step 2 mitigations
    "ADK_MIT_OSCONFIG":      False,   # Apply OsConfig (disable Search/OneDrive/Defender etc.)
}


def _mit(name: str) -> bool:
    """Return True if a mitigation is enabled.

    Priority: environment variable ("0"/"1") > _MITIGATIONS dict default.
    Master switch (ADK_MITIGATIONS) must also be True for any flag to fire.
    """
    def _resolve(key: str) -> bool:
        env = os.getenv(key)
        if env is not None:
            return env == "1"
        return _MITIGATIONS.get(key, True)

    return _resolve("ADK_MITIGATIONS") and _resolve(name)


@pytest.mark.integration
@pytest.mark.requires_windows_adk
@pytest.mark.slow
class TestBPFSWorkflow(BaseTestCase):
    """
    Reboot-survivable end-to-end test for the BPFS Configure Job workflow.

    Inherits BaseTestCase so that setup_teardown_function (autouse) handles
    skip-completed logic automatically on every recovery boot.
    """

    # Class-level state: populated by test_04, consumed by test_05
    _wac_result: "WACRunResult | None" = None
    _osconfig_controller: "OsConfigController | None" = None

    # ------------------------------------------------------------------
    # Class-level fixture — overrides BaseTestCase.setup_teardown_class
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request):
        """Initialise working directory, VersionAdapter, and RebootManager."""
        cls = request.cls
        cls.original_cwd = os.getcwd()

        test_dir = cls._setup_working_directory(__file__)

        # Resolve log path: ADK_LOG_DIR env var or test directory
        base = os.getenv("ADK_LOG_DIR")
        cls.log_path = str(Path(base) / "bpfs_workflow") if base else str(test_dir / "testlog" / "bpfs_workflow")
        Path(cls.log_path).mkdir(parents=True, exist_ok=True)

        cls.adapter = VersionAdapter(get_build_number())
        cls.reboot_mgr = RebootManager(total_tests=cls._count_test_methods())

        phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
        logger.info(f"[SETUP] Phase        : {phase}")
        logger.info(f"[SETUP] reboot_count : {cls.reboot_mgr.state.get('reboot_count', 0)}")
        logger.info(f"[SETUP] completed    : {cls.reboot_mgr.state.get('completed_tests', [])}")
        logger.info(f"[SETUP] log_path     : {cls.log_path}")

        yield

        # Revert OsConfig changes applied in test_02 (best-effort)
        if cls._osconfig_controller is not None:
            try:
                logger.info("[TEARDOWN] Reverting OsConfig changes (pre-reboot path)...")
                cls._osconfig_controller.revert_all()
                logger.info("[TEARDOWN] OsConfig reverted successfully")
            except Exception as exc:
                logger.warning(f"[TEARDOWN] OsConfig revert failed — {exc} (continuing)")
        else:
            state_mgr = OsConfigStateManager()
            if state_mgr.exists():
                try:
                    logger.info("[TEARDOWN] Post-reboot OsConfig revert — loading snapshot from disk")
                    profile = OsConfigProfile(
                        disable_search_index=os.getenv("ADK_DISABLE_SEARCH_INDEX", "0") == "1",
                        disable_onedrive=os.getenv("ADK_DISABLE_ONEDRIVE", "0") == "1",
                        disable_onedrive_tasks=os.getenv("ADK_DISABLE_ONEDRIVE_TASKS", "0") == "1",
                        disable_edge_update_tasks=os.getenv("ADK_DISABLE_EDGE_UPDATE_TASKS", "0") == "1",
                        disable_defender=os.getenv("ADK_DISABLE_DEFENDER", "0") == "1",
                    )
                    controller = OsConfigController(
                        profile=profile,
                        state_manager=state_mgr,
                    )
                    controller.revert_all()
                    logger.info("[TEARDOWN] OsConfig reverted successfully (post-reboot)")
                except Exception as exc:
                    logger.warning(f"[TEARDOWN] OsConfig post-reboot revert failed — {exc} (continuing)")
            else:
                logger.info("[TEARDOWN] No OsConfig snapshot on disk — skipping revert")

        cls._teardown_reboot_manager()
        logger.info(f"{cls.__name__} session complete")
        os.chdir(cls.original_cwd)

    # ------------------------------------------------------------------
    # Step 1 — Precondition (first boot only)
    # ------------------------------------------------------------------

    @pytest.mark.order(1)
    @step(1, "Precondition — clean WAC directories")
    def test_01_precondition(self, adk_env, check_environment):
        """Remove stale WAC result/job/test directories before the run."""
        # Kill any running WAC / assessment engine so file locks are released
        for proc in ("wac.exe", "axe.exe"):
            subprocess.run(["taskkill", "/f", "/im", proc],
                           capture_output=True)
        time.sleep(1)

        # Clear log files so this run starts with a clean app.log.
        # On Phase B (post-reboot) this step is skipped — Phase B logs
        # will be appended to the same app.log written during Phase A.
        clear_log_files()
        Path(self.log_path).mkdir(parents=True, exist_ok=True)

        # Remove stale reboot state so a re-run always starts fresh.
        state_file = Path(RebootManager.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            self.reboot_mgr.state = self.reboot_mgr._load_state()
            logger.info(f"[TEST_01] Removed stale reboot state: {state_file}")

        ctrl = ADKController(config={"log_path": self.log_path})
        ctrl.cleanup_dirs()
        logger.info("[TEST_01] WAC directories cleaned")

        # ── Verify + auto-fix Fast Startup (HiberbootEnabled) ─────────────
        # BPFS assessment requires the system to resume from hibernate via
        # Fast Startup.  If Fast Startup is disabled the OS performs a cold
        # boot instead and the ETW boot-trace session is never written,
        # which causes WAC error 0xC0040477 after the reboot.
        if _mit("ADK_MIT_FAST_STARTUP"):
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Power",
                    access=winreg.KEY_READ | winreg.KEY_WRITE,
                )
                hiberboot, _ = winreg.QueryValueEx(key, "HiberbootEnabled")
                if hiberboot != 1:
                    logger.warning("[TEST_01] Fast Startup disabled — enabling now (HiberbootEnabled=1)")
                    winreg.SetValueEx(key, "HiberbootEnabled", 0, winreg.REG_DWORD, 1)
                    logger.info("[TEST_01] Fast Startup enabled")
                else:
                    logger.info("[TEST_01] Fast Startup already enabled")
                winreg.CloseKey(key)
            except PermissionError:
                pytest.fail(
                    "[TEST_01] Cannot write HiberbootEnabled — run pytest as Administrator."
                )
            except FileNotFoundError:
                logger.warning("[TEST_01] HiberbootEnabled registry key not found — skipping check")
        else:
            logger.info("[TEST_01] ADK_MIT_FAST_STARTUP disabled — skipping Fast Startup check")

        # ── Verify + auto-fix Wake Timers in the active power plan ─────────
        # WAC needs to schedule a wake timer so the system resumes from
        # hibernate automatically.  If wake timers are disabled the machine
        # stays asleep and pytest never gets to Step 4.
        if _mit("ADK_MIT_WAKE_TIMERS"):
            try:
                result = subprocess.run(
                    ["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE"],
                    capture_output=True, text=True,
                )
                if "0x00000001" in result.stdout:
                    logger.info("[TEST_01] Wake timers enabled in active power plan")
                else:
                    logger.warning("[TEST_01] Wake timers disabled — enabling for AC and DC")
                    subprocess.run(
                        ["powercfg", "/setacvalueindex", "SCHEME_CURRENT",
                         "SUB_SLEEP", "RTCWAKE", "1"],
                        capture_output=True,
                    )
                    subprocess.run(
                        ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT",
                         "SUB_SLEEP", "RTCWAKE", "1"],
                        capture_output=True,
                    )
                    subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"], capture_output=True)
                    logger.info("[TEST_01] Wake timers enabled")
            except Exception as exc:
                logger.warning(f"[TEST_01] Wake timer check failed (non-fatal): {exc}")
        else:
            logger.info("[TEST_01] ADK_MIT_WAKE_TIMERS disabled — skipping wake timer check")

        # ── Ensure ETW-dependent services are running ───────────────────────
        # BPFS relies on an ETW boot autologger session that stays alive for
        # ~120 s after Fast Startup resume.  Two services maintain that session:
        #   SysMain  (Superfetch) — manages boot profiling / ETW boot session
        #   DiagTrack             — Connected User Experiences and Telemetry
        # If either is stopped/disabled the ETW session can disappear during the
        # 120-second post-boot tracing window, causing WAC error 0xC0040477.
        for svc in ("SysMain", "DiagTrack"):
            try:
                status_result = subprocess.run(
                    ["sc", "query", svc],
                    capture_output=True, text=True,
                )
                if "RUNNING" in status_result.stdout:
                    logger.info(f"[TEST_01] Service '{svc}' is running")
                else:
                    logger.warning(f"[TEST_01] Service '{svc}' is not running — attempting to start")
                    start_result = subprocess.run(
                        ["sc", "start", svc],
                        capture_output=True, text=True,
                    )
                    if start_result.returncode == 0:
                        logger.info(f"[TEST_01] Service '{svc}' started successfully")
                    else:
                        logger.warning(
                            f"[TEST_01] Could not start '{svc}': {start_result.stderr.strip()} "
                            f"(BPFS ETW session may expire mid-assessment)"
                        )
                # Also ensure the service start type is not Disabled
                config_result = subprocess.run(
                    ["sc", "qc", svc],
                    capture_output=True, text=True,
                )
                if "DISABLED" in config_result.stdout:
                    logger.warning(
                        f"[TEST_01] Service '{svc}' start type is DISABLED — "
                        f"setting to DEMAND_START so it survives reboots"
                    )
                    subprocess.run(
                        ["sc", "config", svc, "start=", "demand"],
                        capture_output=True,
                    )
            except Exception as exc:
                logger.warning(f"[TEST_01] Service check for '{svc}' failed (non-fatal): {exc}")

        # ── Refresh the hibernate file ────────────────────────────────
        # A stale hibernate file from a previous WAC run can leave ETW
        # autologger entries in a partial state.  On the next hibernate this
        # causes the boot-trace session to disappear mid-assessment
        # (0xC0040477).  Disabling and re-enabling hibernate forces Windows
        # to create a fresh hiberfil.sys and clears any stale session state.
        if _mit("ADK_MIT_HIBERFIL"):
            try:
                subprocess.run(["powercfg", "/hibernate", "off"], capture_output=True, check=True)
                subprocess.run(["powercfg", "/hibernate", "on"],  capture_output=True, check=True)
                logger.info("[TEST_01] Hibernate file refreshed (off/on)")
            except Exception as exc:
                logger.warning(f"[TEST_01] Hibernate refresh failed (non-fatal): {exc}")
        else:
            logger.info("[TEST_01] ADK_MIT_HIBERFIL disabled — skipping hibernate file refresh")

        # ── Log active ETW autologger sessions (diagnostic) ────────────────
        # This output helps identify left-over sessions from previous runs
        # that might conflict with WAC's own autologger registration.
        try:
            al_result = subprocess.run(
                ["logman", "query", "autologgers"],
                capture_output=True, text=True, timeout=15,
            )
            logger.info("[TEST_01] Active autologger sessions:\n%s", al_result.stdout.strip())
        except Exception as exc:
            logger.warning(f"[TEST_01] logman query autologgers failed (non-fatal): {exc}")

    # ------------------------------------------------------------------
    # Step 2 — Apply OS configuration
    # ------------------------------------------------------------------

    @pytest.mark.order(2)
    @step(2, "OsConfig — apply OS settings")
    def test_02_apply_osconfig(self, adk_env, check_environment):
        """
        Apply OS configuration for clean BPFS testing.
        Settings are controlled via environment variables (all default to disabled).

        Environment variables:
            ADK_DISABLE_SEARCH_INDEX      Set to "1" to disable Windows Search service.
            ADK_DISABLE_ONEDRIVE          Set to "1" to disable OneDrive via policy.
            ADK_DISABLE_ONEDRIVE_TASKS    Set to "1" to disable OneDrive scheduled tasks.
            ADK_DISABLE_EDGE_UPDATE_TASKS Set to "1" to disable Edge update tasks.
            ADK_DISABLE_DEFENDER          Set to "1" to disable Defender real-time protection.
        """
        logger.info("[TEST_02] OsConfig apply started")

        if not _mit("ADK_MIT_OSCONFIG"):
            logger.info("[TEST_02] ADK_MIT_OSCONFIG disabled — skipping OsConfig apply")
            return

        profile = OsConfigProfile(
            disable_search_index=os.getenv("ADK_DISABLE_SEARCH_INDEX", "0") == "1",
            disable_onedrive=os.getenv("ADK_DISABLE_ONEDRIVE", "0") == "1",
            disable_onedrive_tasks=os.getenv("ADK_DISABLE_ONEDRIVE_TASKS", "0") == "1",
            disable_edge_update_tasks=os.getenv("ADK_DISABLE_EDGE_UPDATE_TASKS", "0") == "1",
            disable_defender=os.getenv("ADK_DISABLE_DEFENDER", "0") == "1",
        )
        controller = OsConfigController(
            profile=profile,
            state_manager=OsConfigStateManager(),
        )
        controller.apply_all()

        # Cache for teardown revert (best-effort)
        TestBPFSWorkflow._osconfig_controller = controller

        logger.info("[TEST_02] OsConfig applied successfully")

    # ------------------------------------------------------------------
    # Step 3 — Configure BPFS and click Start (triggers hibernate)
    # ------------------------------------------------------------------

    @pytest.mark.order(3)
    @step(3, "Configure BPFS and click Start")
    def test_03_configure_and_start(self, adk_env, check_environment):
        """
        Open WAC, configure BPFS with Iterations=1, save the custom job,
        connect the Assessment Launcher.

        RebootManager.prepare_for_external_reboot() is called BEFORE
        click_start() so that state is persisted and the auto-start BAT is
        written while the process is still running.  WAC hibernates the
        machine immediately after Start; pytest auto-resumes at Step 3.
        """
        job_name = os.getenv("ADK_BPFS_JOB_NAME", "BPFS_Workflow_Test")
        ctrl = ADKController(config={"log_path": self.log_path})

        ctrl._ui.open(WAC_EXE)
        ctrl._ui.select_bpfs_configured_job(num_iters=1, auto_boot=True)
        ctrl._ui.save_custom_job(job_name)
        ctrl._ui.connect_launcher()

        # Persist state BEFORE clicking Start — the machine will hibernate.
        self.reboot_mgr.prepare_for_external_reboot(
            step_name="test_03_configure_and_start",
            test_file=__file__,
        )

        logger.info("[TEST_03] Clicking Start — machine will hibernate shortly")
        ctrl._ui.click_start()

        # Fallback wait in case hibernate is delayed (e.g. dry-run environment).
        # Wall-clock detection: if the 120-second sleep actually takes >>120 s
        # of real time, the machine hibernated and resumed mid-sleep.  In that
        # case a second pytest process has already been started by the startup
        # BAT.  Exit this (original) process to prevent duplicate test_04
        # execution which can interfere with WAC's UI automation.
        logger.info("[TEST_03] Waiting for hibernate...")
        _t_click = time.time()
        time.sleep(120)
        _wall = time.time() - _t_click
        if _wall > 300:
            logger.info(
                "[TEST_03] Hibernate detected (wall time=%.0fs) — "
                "exiting so startup BAT handles test_04+", _wall
            )
            os._exit(0)

    # ------------------------------------------------------------------
    # Step 4 — Wait for assessment result (runs after reboot)
    # ------------------------------------------------------------------

    @pytest.mark.order(4)
    @step(4, "Wait for WAC assessment result")
    def test_04_wait_result(self, adk_env, check_environment):
        """
        Connect to WAC after the post-BPFS reboot and wait for the
        View Results page to appear.

        WAC auto-resumes the assessment on wakeup; when finished it
        switches to the View Results page.  We read:
          - Total errors / warnings from the Run information grid
          - The Results filesystem path from the System information panel

        Pass criteria: errors == 0.
        """
        timeout = int(os.getenv("ADK_BPFS_TIMEOUT", "7200"))
        ctrl = ADKController(config={"log_path": self.log_path})

        # ── Verify this was a Fast Startup resume, not a cold boot ────────
        # If the system did a cold boot instead of a hibernate resume the ETW
        # boot-trace session won't exist and WAC will report 0xC0040477.
        # We detect this early via Kernel-Power Event ID 1 in the System log.
        # Event ID 1 data[0]=1  → Fast Startup resume (hibernate)
        # Event ID 1 data[0]=2  → Cold boot
        # (absent entirely = still booting, treat as unknown)
        try:
            ps_check = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-WinEvent -LogName System -MaxEvents 300 "
                    "| Where-Object { $_.Id -eq 1 -and $_.ProviderName -eq "
                    "'Microsoft-Windows-Kernel-Power' } "
                    "| Select-Object -First 1 -ExpandProperty Properties "
                    "| Select-Object -First 1 -ExpandProperty Value",
                ],
                capture_output=True, text=True, timeout=30,
            )
            boot_type = ps_check.stdout.strip()
            if boot_type == "2":
                pytest.fail(
                    "[TEST_04] System performed a COLD BOOT instead of a Fast Startup resume.\n"
                    "The ETW boot-trace session will not exist and WAC will fail with 0xC0040477.\n"
                    "Probable causes:\n"
                    "  - Fast Startup was disabled at boot time\n"
                    "  - Wake timer did not fire (machine was powered on manually)\n"
                    "  - Hibernate file was discarded by the firmware\n"
                    "Re-run from Step 1 to retry."
                )
            elif boot_type == "1":
                logger.info("[TEST_04] Boot type confirmed: Fast Startup resume (hibernate)")
            else:
                logger.warning(f"[TEST_04] Boot type unknown (value={boot_type!r}) — proceeding")
        except Exception as exc:
            logger.warning(f"[TEST_04] Boot-type check failed (non-fatal): {exc}")

        # debug_enumerate=True logs all UI element IDs on first run.
        # Flip to False once auto_ids are confirmed on this build.
        wac_result = ctrl._ui.read_view_results(
            timeout=timeout,
            debug_enumerate=True,
        )

        logger.info(
            "[TEST_04] errors=%d  warnings=%d  analysis_complete=%s",
            wac_result.errors, wac_result.warnings, wac_result.analysis_complete,
        )
        logger.info("[TEST_04] machine      : %s", wac_result.machine_name)
        logger.info("[TEST_04] run_time     : %s", wac_result.run_time)
        logger.info("[TEST_04] result_path  : %s", wac_result.result_path)

        # Store for step 5 verification
        TestBPFSWorkflow._wac_result = wac_result

        assert wac_result.errors == 0, (
            f"BPFS assessment completed with {wac_result.errors} error(s). "
            f"Results path: {wac_result.result_path}"
        )

    # ------------------------------------------------------------------
    # Step 5 — Verify result artefacts
    # ------------------------------------------------------------------

    @pytest.mark.order(5)
    @step(5, "Verify result artefacts")
    def test_05_verify(self, adk_env, check_environment):
        """Assert expected result files exist using the path reported by WAC."""
        wac_result = getattr(TestBPFSWorkflow, "_wac_result", None)

        assert wac_result is not None, (
            "test_04_wait_result did not store a WACRunResult — "
            "ensure test_04 ran and passed before test_05."
        )
        assert wac_result.result_path, (
            f"WAC did not report a Results path. "
            f"errors={wac_result.errors}  warnings={wac_result.warnings}\n"
            "Check app.log for [ViewResults DEBUG] entries to diagnose."
        )

        result_dir = Path(wac_result.result_path)
        assert result_dir.is_dir(), (
            f"WAC Results directory does not exist: {result_dir}"
        )

        axelog = result_dir / "AxeLog.txt"
        assert axelog.exists(), f"AxeLog.txt not found in {result_dir}"
        logger.info(f"[TEST_05] AxeLog.txt verified: {axelog}")

