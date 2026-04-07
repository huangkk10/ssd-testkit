"""
Reboot manager - handles system reboots and recovery state

Responsibilities:
- Persist and load reboot/test state
- Create an auto-start entry so the packaged test runner resumes after reboot
- Track completed tests to avoid re-running steps after recovery
"""
import json
import logging
import os
import subprocess
import sys
import traceback
from pathlib import Path
import getpass
import pytest

_log = logging.getLogger(__name__)

_UNSET = object()  # sentinel for auto_login_config default

class RebootManager:
    """
    Manage test reboot workflow

    Features:
    - Save and restore state across reboots
    - Create startup auto-run so the packaged runner resumes after reboot
    - Track which tests have completed to avoid loops on recovery
    """
    
    STATE_FILE = "./pytest_reboot_state.json"
    # VBS in Startup folder — wscript.exe needs far fewer DLLs than cmd.exe
    # and can successfully WScript.Sleep before cmd.exe is safe to launch.
    STARTUP_VBS_PATH = r"C:\Users\{}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\pytest_auto_run.vbs"
    # BAT stored in working directory (NOT in Startup folder)
    BAT_FILENAME = "pytest_auto_run.bat"
    # Legacy path kept for cleanup of old installations
    STARTUP_PATH = r"C:\Users\{}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\pytest_auto_run.bat"
    
    def __init__(self, total_tests: int = 5, auto_login_config=None):
        self.state_file = self.STATE_FILE
        self.total_tests = total_tests
        self._auto_login_config = auto_login_config if auto_login_config is not None else {}
        # Auto-clear stale state when this is a fresh manual run (not a
        # BAT-triggered recovery).  The startup BAT always sets
        # PYTEST_REBOOT_RECOVERY=1; its absence means the user ran pytest
        # directly, so any leftover state file is stale and should be removed.
        if not os.environ.get('PYTEST_REBOOT_RECOVERY') and Path(self.state_file).exists():
            Path(self.state_file).unlink()
        # On BAT-triggered recovery, clear any stale lock file left by the
        # previous session process being killed by an OS reboot mid-run.
        # Without this, the BAT's duplicate-launch guard blocks subsequent
        # reboot cycles (e.g. BPFS training run → calibration run).
        if os.environ.get('PYTEST_REBOOT_RECOVERY'):
            lock_file = Path(os.getcwd()) / ".pytest_running.lock"
            if lock_file.exists():
                lock_file.unlink()
                _log.info("[RebootManager] Cleared stale lock file: %s", lock_file)
        self.state = self._load_state()
    
    def _load_state(self):
        """Load persisted state from the state file."""
        if Path(self.state_file).exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            # backward-compat: old state files won't have these keys
            state.setdefault("step_reboot_counts", {})
            state.setdefault("loop_groups", {})
            state.setdefault("external_reboot_pending", False)
            return state
        return {
            "completed_tests": [],
            "is_recovering": False,
            "current_test": None,
            "reboot_count": 0,
            "step_reboot_counts": {},
            "loop_groups": {},
            "external_reboot_pending": False,
        }
    
    def _save_state(self):
        """Persist state to disk (flush and fsync to ensure durability)."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    
    def is_recovering(self):
        """Return True if current run is a recovery after reboot."""
        return self.state.get("is_recovering", False)
    
    def is_completed(self, test_name):
        """Return True if the given test name is recorded as completed."""
        return test_name in self.state["completed_tests"]
    
    def mark_completed(self, test_name):
        """Mark a test as completed and clear the recovering flag."""
        if test_name not in self.state["completed_tests"]:
            self.state["completed_tests"].append(test_name)
        self.state["is_recovering"] = False
        self._save_state()

    def require_rebooted(self, min_count: int = 1) -> None:
        """
        Assert that at least *min_count* reboots have been performed.

        Calls pytest.fail() if the condition is not met, making the test
        a hard failure rather than a silent skip.

        Usage (in any test body):
            self.reboot_mgr.require_rebooted()         # reboot_count >= 1
            self.reboot_mgr.require_rebooted(2)        # reboot_count >= 2

        Args:
            min_count: Minimum number of reboots required (default 1).

        Note:
            Prefer require_after() when possible — it expresses the dependency
            by predecessor test name rather than a raw counter, which is more
            robust when the test flow changes.
        """
        actual = self.state.get("reboot_count", 0)
        if actual < min_count:
            pytest.fail(
                f"Reboot prerequisite not met: expected reboot_count >= {min_count}, "
                f"got {actual}. Ensure the reboot step completed successfully before "
                "this step runs."
            )

    def require_after(self, predecessor: str) -> None:
        """
        Assert that *predecessor* test has already been completed.

        Preferred over require_rebooted(min_count=N) because it expresses the
        dependency by name rather than a magic number.  If the reboot sequence
        is refactored (steps added/removed), only the predecessor name needs
        updating rather than hunting for every hardcoded count.

        Calls pytest.fail() (not skip) so a missing predecessor is reported as
        a test-flow error, not silently hidden.

        Usage:
            # test_10 must only run after the second reboot step (test_09)
            self.reboot_mgr.require_after("test_09_clear_sleepstudy_and_reboot")

        Args:
            predecessor: Exact pytest node name of the required predecessor step.
        """
        if not self.is_completed(predecessor):
            pytest.fail(
                f"Prerequisite step not completed: '{predecessor}' must run "
                "before this step. Ensure the reboot sequence ran in order."
            )

    def pre_mark_completed(self, test_name: str) -> None:
        """Mark a test as completed without toggling the recovering flag.

        This is used by tests that call `setup_reboot()` which terminates the
        process immediately (os._exit(0)). The pre-mark ensures the test is
        recorded as completed so it won't re-run after recovery.
        """
        if test_name not in self.state["completed_tests"]:
            self.state["completed_tests"].append(test_name)
        self._save_state()

    def prepare_for_external_reboot(self, step_name: str, test_file: str = None) -> None:
        """Prepare state for a reboot triggered externally (e.g. WAC BPFS hibernate).

        Unlike setup_reboot(), this method does NOT schedule a shutdown command
        and does NOT call os._exit().  The caller is responsible for triggering
        the reboot (e.g. clicking Start in WAC).  This method only persists state
        and writes the auto-start BAT so pytest resumes after the system boots.

        Call this BEFORE the action that triggers hibernate/reboot.

        Args:
            step_name: The current test function name.  Will be pre-marked as
                       completed so it is skipped on the next pytest run.
            test_file: Pass __file__ so the auto-start BAT relaunches the
                       correct test file after the system boots.
        """
        self.state["is_recovering"] = True
        self.state["external_reboot_pending"] = True  # preserved until end_external_reboot_sequence()
        self.state["reboot_count"] += 1
        if step_name not in self.state["completed_tests"]:
            self.state["completed_tests"].append(step_name)
        self._save_state()
        self._setup_auto_start(test_file)
        _log.info("[RebootManager] prepare_for_external_reboot: step='%s'", step_name)
        _log.info("[RebootManager] State persisted — reboot_count=%s", self.state['reboot_count'])
        _log.info("[RebootManager] Auto-start BAT written (will resume after reboot)")

    # ------------------------------------------------------------------
    # Multi-reboot API
    # ------------------------------------------------------------------

    def _get_step_reboot_count(self, step_name: str) -> int:
        """Return the number of reboots already performed for *step_name*."""
        return self.state.setdefault("step_reboot_counts", {}).get(step_name, 0)

    def _increment_step_reboot_count(self, step_name: str) -> int:
        """Increment and persist the per-step reboot counter. Returns new value."""
        counts = self.state.setdefault("step_reboot_counts", {})
        counts[step_name] = counts.get(step_name, 0) + 1
        return counts[step_name]

    def reboot_cycles(
        self,
        count: int,
        *,
        request,
        test_file: str,
        delay: int = 10,
        reason: str = "",
    ) -> None:
        """
        Perform *count* consecutive reboots for the calling test step, then
        return so that the rest of the test body can execute.

        Each time the system reboots and pytest resumes, all previously
        completed steps remain in ``completed_tests`` and are skipped
        automatically.  The calling step is **not** marked completed until
        ``reboot_cycles`` returns, which happens only after the Nth reboot.

        Usage (the entire multi-reboot logic fits in one line)::

            def test_02_reboot_cycles(self, request):
                self.reboot_mgr.reboot_cycles(3, request=request, test_file=__file__)
                # Execution reaches here only after 3 successful reboots

        Args:
            count:      Total number of reboots required.
            request:    The pytest ``request`` fixture (used to obtain the
                        step name via ``request.node.name``).
            test_file:  Pass ``__file__`` so the auto-start BAT relaunches
                        the correct test file after each reboot.
            delay:      Seconds before the system shuts down (default 10).
            reason:     Optional log message prefix shown at reboot time.
        """
        step_name = request.node.name
        current = self._get_step_reboot_count(step_name)

        if current < count:
            new_count = self._increment_step_reboot_count(step_name)
            _reason = reason or f"{step_name}: reboot cycle {new_count}/{count}"
            self.setup_reboot(
                delay=delay,
                reason=_reason,
                test_file=test_file,
            )
            # setup_reboot calls os._exit(0) — code below never executes

        # All required reboots completed — clean up the per-step counter
        # and let the test body continue.  mark_completed() will be called
        # automatically by BaseTestCase.setup_teardown_function teardown.
        self.state.get("step_reboot_counts", {}).pop(step_name, None)
        self._save_state()

    def loop_next(
        self,
        group: str,
        *,
        total: int,
        steps: list,
        request=None,
        test_file: str = None,
        reboot: bool = True,
        delay: int = 10,
        reason: str = "",
    ) -> None:
        """
        Advance a named loop group by one round, then either reboot or return.

        Call this at the **end** of the last step in a repeating block.
        The steps listed in *steps* are removed from ``completed_tests`` so
        they will execute again on the next round.  When the final round
        finishes, the method returns normally and execution continues with
        whatever test follows in the collection order.

        Usage::

            # test_04 is the last step of the loop block
            def test_04_end_of_loop(self, request):
                # ... test body ...
                self.reboot_mgr.loop_next(
                    "main_loop",
                    total=3,
                    steps=["test_02_step_a", "test_03_step_b", "test_04_end_of_loop"],
                    request=request,
                    test_file=__file__,   # required when reboot=True
                )
                # Reached here only on the final round — test_05 follows.

        Args:
            group:      Unique name for this loop (supports multiple independent
                        loops in the same test class).
            total:      Total number of rounds to execute.
            steps:      Test names whose ``completed_tests`` entry is cleared at
                        the end of each non-final round so they re-execute.
            request:    pytest ``request`` fixture (used for logging only;
                        may be ``None``).
            test_file:  Pass ``__file__``; required when ``reboot=True``.
            reboot:     ``True`` (default) — reboot after each non-final round.
                        ``False`` — return immediately; the same pytest session
                        continues and unreached steps will re-run because they
                        are no longer in ``completed_tests``.
            delay:      Seconds before shutdown (only used when reboot=True).
            reason:     Log message shown at reboot time.
        """
        groups = self.state.setdefault("loop_groups", {})
        current_round = groups.get(group, {}).get("current_round", 0)

        step_label = request.node.name if request is not None else group

        if current_round < total - 1:
            # Advance to the next round
            current_round += 1
            groups[group] = {"current_round": current_round, "total_rounds": total}

            # Remove loop steps from completed_tests so they re-execute
            completed = self.state["completed_tests"]
            for s in steps:
                if s in completed:
                    completed.remove(s)

            self._save_state()

            if reboot:
                _reason = reason or (
                    f"{step_label}: loop '{group}' round {current_round}/{total - 1}"
                )
                self.setup_reboot(delay=delay, reason=_reason, test_file=test_file)
                # setup_reboot calls os._exit(0) — code below never executes
            # reboot=False: return so pytest continues in the same session
            return

        # Final round complete — clean up this group and return
        groups.pop(group, None)
        self._save_state()

    def all_tests_completed(self):
        """Return True when the number of completed tests >= total_tests."""
        return len(self.state["completed_tests"]) >= self.total_tests
    
    def setup_reboot(self, delay=10, reason="System reboot required", test_file=None, auto_login_config=_UNSET):
        """
        Configure and trigger a system reboot.

        Args:
            delay: Seconds before reboot.
            reason: Human-readable reason for logs.
            test_file: Path to the test file to run on recovery (written into
                       the startup script so the packaged runner resumes the
                       right test file after the system boots).
        """
        _log.info("[RebootManager] setup_reboot called: delay=%s reason=%s", delay, reason)

        # Ensure auto-login is set so the system resumes the test after reboot
        # Default: use the config supplied at __init__ time (pass None to skip).
        if auto_login_config is _UNSET:
            auto_login_config = self._auto_login_config
        if auto_login_config is not None:
            try:
                from lib.testtool.osconfig.actions.auto_admin_logon import AutoAdminLogonAction
                _al = AutoAdminLogonAction(
                    username=auto_login_config.get('auto_login_username') or None,
                    password=auto_login_config.get('auto_login_password') or None,
                    domain=auto_login_config.get('auto_login_domain') or None,
                )
                if not _al.check():
                    _log.info('[RebootManager] Auto-login not enabled - applying AutoAdminLogon')
                    _al.apply()
                    _log.info('[RebootManager] AutoAdminLogon applied')
                else:
                    _log.info('[RebootManager] Auto-login already enabled - skipping')
            except Exception as _exc:
                _log.warning('[RebootManager] auto-login check/apply failed: %s\n%s',
                             _exc, traceback.format_exc())

        # Mark that we're about to reboot and persist state
        self.state["is_recovering"] = True
        self.state["reboot_count"] += 1
        try:
            self._save_state()
            _log.info("[RebootManager] State saved (reboot_count=%s)", self.state["reboot_count"])
        except Exception as _exc:
            _log.error("[RebootManager] _save_state failed: %s\n%s", _exc, traceback.format_exc())
            raise

        # Create a startup entry so the packaged runner will resume after boot
        try:
            self._setup_auto_start(test_file)
            _log.info("[RebootManager] Auto-start script written")
        except Exception as _exc:
            _log.error("[RebootManager] _setup_auto_start failed: %s\n%s", _exc, traceback.format_exc())
            raise

        # Informational messages
        _log.info("[Reboot] %s — system will reboot in %s seconds", reason, delay)

        # Execute the reboot command
        # First cancel any pending shutdown from a previous interrupted run
        # so that our new "shutdown /r /t delay" is not rejected with
        # "A system shutdown is already in progress" (exit code 1190).
        _cancel = subprocess.run(
            ["shutdown", "/a"],
            capture_output=True, text=True
        )
        if _cancel.returncode == 0:
            _log.info("[RebootManager] Cancelled pending shutdown before issuing new reboot")
        else:
            _log.info("[RebootManager] shutdown /a returned rc=%s (no pending shutdown to cancel)", _cancel.returncode)
        try:
            result = subprocess.run(
                ["shutdown", "/r", "/t", str(delay)],
                capture_output=True,
                text=True,
                check=True
            )
            _log.info("[RebootManager] Reboot command executed successfully")
            if result.stdout:
                _log.info("[RebootManager] shutdown output: %s", result.stdout.strip())
        except subprocess.CalledProcessError as e:
            _log.error(
                "[RebootManager] shutdown /r failed (rc=%s): %s",
                e.returncode, e.stderr.strip() if e.stderr else str(e)
            )
            raise

        # Immediately terminate the process to avoid any teardown that might
        # remove the startup script or state file.  This guarantees the recovery
        # data remains on disk for the post-boot execution.
        _log.info("[RebootManager] Forcing process exit - system will reboot shortly...")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    
    def _setup_auto_start(self, test_file=None):
        """Write the Startup VBS wrapper and the recovery BAT file.

        Two files are created:

        VBS (Windows Startup folder, run by wscript.exe):
            wscript.exe needs far fewer DLLs than cmd.exe and initialises
            earlier during Fast Startup resume.  The VBS sleeps 60 seconds
            (Phase 1) so that all DLLs are ready before cmd.exe is called,
            preventing the 0xc0000142 STATUS_DLL_INIT_FAILED crash.

        BAT (working directory):
            Handles Phase 2 (FAS.exe / BPFS guard) and Phase 3 (stale-lock
            detection + pytest invocation).  cmd.exe is safe to run by the
            time the VBS calls it (60 s have elapsed).
        """
        user = getpass.getuser()
        vbs_path = self.STARTUP_VBS_PATH.format(user)
        current_dir = os.getcwd()
        bat_path = os.path.join(current_dir, self.BAT_FILENAME)

        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            exe = sys.executable
            cmd_args = '-v'
            if test_file:
                cmd_args += f' --test "{test_file}"'
            run_cmd = f'"{exe}" {cmd_args}'
        else:
            python_exe = sys.executable
            pytest_args = '-v --tb=short'
            if test_file:
                pytest_args += f' "{test_file}"'
            run_cmd = f'"{python_exe}" -m pytest {pytest_args}'

        log_level = os.environ.get('LOG_LEVEL', '')
        log_level_line = f'set LOG_LEVEL={log_level}' if log_level else ''
        recovery_marker = 'set PYTEST_REBOOT_RECOVERY=1'
        lock_file = os.path.join(current_dir, '.pytest_running.lock')

        # -- VBS: Startup folder entry (wscript.exe) --------------------------
        # wscript.exe loads before cmd.exe is safe to start during Fast Startup
        # resume.  WScript.Sleep 60000 gives DLLs time to fully initialise.
        # Phase 2+3 remain in the BAT; the VBS just delays and then calls it.
        vbs_lines = [
            "' pytest_auto_run.vbs -- auto-generated by RebootManager",
            "' Phase 1: 60-second DLL-initialisation delay",
            "' wscript.exe starts before cmd.exe/python.exe are safe during Fast Startup resume.",
            "' After 60 s all DLLs are ready; cmd.exe can launch without 0xc0000142.",
            'WScript.Sleep 60000',
            '',
            "' Launch the recovery BAT (Phase 2: FAS.exe guard; Phase 3: stale-lock + pytest)",
            'Dim oShell : Set oShell = CreateObject("WScript.Shell")',
            f'oShell.Run "cmd /c " & Chr(34) & "{bat_path}" & Chr(34), 1, False',
        ]
        vbs_content = '\n'.join(vbs_lines) + '\n'

        # -- BAT: working-directory script (cmd.exe) --------------------------
        # Phase 1 is handled by the VBS; BAT handles Phase 2 (FAS.exe check)
        # and Phase 3 (stale-lock guard + pytest launch).
        bat_lines = [
            '@echo off',
            f'cd /d {current_dir}',
            '',
            ':: -- Phase 2: BPFS Fast-Startup guard --',
            ':: FAS.exe is alive during BPFS training iterations; exit to avoid',
            ':: launching a second pytest that conflicts with the ongoing assessment.',
            'tasklist /FI "IMAGENAME eq FAS.exe" /NH 2>nul | find /i "FAS.exe" >nul 2>&1',
            'if not errorlevel 1 (',
            '    echo [AutoRun] FAS.exe detected - BPFS resume, exiting',
            '    exit /b 0',
            ')',
            '',
            ':: -- Phase 3: Stale-lock guard --',
            ':: If the lock exists but python.exe is gone the lock is stale; clear it.',
            f'set LOCK={lock_file}',
            'if exist "%LOCK%" (',
            '    tasklist /FI "IMAGENAME eq python.exe" /NH 2>nul | find /i "python.exe" >nul 2>&1',
            '    if errorlevel 1 (',
            '        echo [AutoRun] Stale lock detected - clearing',
            '        del "%LOCK%" 2>nul',
            '    ) else (',
            '        echo [AutoRun] pytest already running - skipping',
            '        exit /b 0',
            '    )',
            ')',
            'echo %TIME% > "%LOCK%"',
            '',
            recovery_marker,
            log_level_line,
            run_cmd,
            '',
            'del "%LOCK%" 2>nul',
        ]
        bat_content = '\n'.join(bat_lines) + '\n'

        os.makedirs(os.path.dirname(vbs_path), exist_ok=True)
        with open(vbs_path, 'w', encoding='utf-8') as f:
            f.write(vbs_content)
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)

        _log.info('[RebootManager] Startup VBS created: %s', vbs_path)
        _log.info('[RebootManager] Recovery BAT created: %s', bat_path)
        if test_file:
            _log.info('[RebootManager] Will resume test file: %s', test_file)

    def end_external_reboot_sequence(self) -> None:
        """Signal that the external reboot sequence (e.g. WAC BPFS/S4/S5) is
        fully complete and the startup BAT / state file may be removed on the
        next teardown.

        Call this from the test step that collects the final WAC results
        (e.g. test_11_wait_results) so that subsequent teardown is safe to
        call cleanup().
        """
        self.state["external_reboot_pending"] = False
        self._save_state()
        _log.info("[RebootManager] external_reboot_pending cleared — cleanup allowed on teardown")

    def cleanup(self):
        """Remove persisted state and auto-start scripts (if present)."""

        # Remove the state file
        if Path(self.state_file).exists():
            os.remove(self.state_file)
            _log.info("[RebootManager] State file removed: %s", self.state_file)

        user = getpass.getuser()

        # Remove VBS from the Startup folder (new approach)
        vbs_path = self.STARTUP_VBS_PATH.format(user)
        if os.path.exists(vbs_path):
            os.remove(vbs_path)
            _log.info("[RebootManager] Startup VBS removed: %s", vbs_path)

        # Remove BAT from the working directory (new approach)
        bat_path = os.path.join(os.getcwd(), self.BAT_FILENAME)
        if os.path.exists(bat_path):
            os.remove(bat_path)
            _log.info("[RebootManager] Recovery BAT removed: %s", bat_path)

        # Legacy: also remove old-style BAT from Startup folder (backward compat)
        old_bat_path = self.STARTUP_PATH.format(user)
        if os.path.exists(old_bat_path):
            os.remove(old_bat_path)
            _log.info("[RebootManager] Legacy Startup BAT removed: %s", old_bat_path)

        _log.info("[RebootManager] Cleanup completed")
