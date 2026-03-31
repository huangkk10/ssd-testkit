"""
Base test class — all test cases should inherit from this class.
Provides standard setup/teardown hooks and test state management.
"""
import inspect
import os
import pytest
import shutil
from pathlib import Path
from framework.reboot_manager import RebootManager
from framework.test_utils import setup_test_environment, cleanup_test_environment
import lib.logger as logger
from lib.logger import logConfig, write_session_footer

class BaseTestCase:
    """
    Base test class

    Usage:
        class TestYourCase(BaseTestCase):
            def test_step_01(self):
                # test logic
                pass
    """
    
    # ========== Class-level Setup/Teardown ==========
    @pytest.fixture(scope="class", autouse=True)
    def setup_teardown_class(self, request):
        """Class-level setup and teardown"""
        # Setup：初始化測試環境
        cls = request.cls
        cls.test_name = request.node.name
        cls.log_path = "./testlog"
        cls.reboot_mgr = RebootManager()
        
        # Only initialize on first run (skip during recovery)
        if not cls.reboot_mgr.is_recovering():
            logger.LogEvt("=" * 60)
            logger.LogEvt(f"Setting up test: {cls.test_name}")
            logger.LogEvt("=" * 60)
            
            # Clean up testlog directory (framework standard behavior)
            cls._cleanup_testlog_directory()
            
            setup_test_environment(cls.log_path)
        else:
            logger.LogEvt("=" * 60)
            logger.LogEvt(f"Recovering test: {cls.test_name}")
            logger.LogEvt("=" * 60)
        
        yield  # test execution
        
        # Teardown: clean up test environment
        if cls.reboot_mgr.all_tests_completed():
            logger.LogEvt("=" * 60)
            logger.LogEvt("All tests completed, cleaning up...")
            logger.LogEvt("=" * 60)
            cleanup_test_environment()
            cls.reboot_mgr.cleanup()
    
    # ========== Function-level Setup/Teardown ==========
    @pytest.fixture(autouse=True)
    def setup_teardown_function(self, request):
        """Function-level setup and teardown"""
        test_name = request.node.name
        # Setup: check whether this test should be skipped
        if self.reboot_mgr.is_completed(test_name):
            pytest.skip(f"{test_name} already completed")
        
        logger.LogEvt(f"--- Starting: {test_name} ---")
        
        yield  # test execution
        
        # Teardown: mark as completed
        logger.LogEvt(f"--- Completed: {test_name} ---")
        self.reboot_mgr.mark_completed(test_name)
    
    # ========== Helper methods ==========
    @classmethod
    def _count_test_methods(cls) -> int:
        """Return the number of test_* methods defined on the class."""
        return sum(
            1 for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
            if name.startswith('test_')
        )

    @classmethod
    def _setup_working_directory(cls, caller_file: str) -> Path:
        """
        Resolve the test working directory (packaged vs development) and chdir into it.
        Also initialises the logging system via logConfig().

        Args:
            caller_file: Pass ``__file__`` from the subclass fixture so that the
                         development-mode fallback points to the correct directory.

        Returns:
            Resolved test_dir Path (already set as cwd).
        """
        try:
            from path_manager import path_manager
            test_dir = Path(path_manager.app_dir)
            logger.LogEvt(f"[SETUP] Packaged environment: {test_dir}")
        except ImportError:
            test_dir = Path(caller_file).parent
            logger.LogEvt(f"[SETUP] Development environment: {test_dir}")
        # Always chdir to the testcase directory so that relative paths like
        # "./Config/Config.json" resolve correctly in both modes.
        os.chdir(Path(caller_file).parent)
        logConfig()
        return test_dir

    @classmethod
    def _init_runcard(cls, runcard_params: dict) -> None:
        """
        Initialise RunCard and call start_test.  Sets ``cls.runcard``.
        Failures are non-fatal — ``cls.runcard`` is set to ``None`` on error.

        Args:
            runcard_params: Dict with keys ``'initialization'`` and ``'start_params'``
                            as expected by the RunCard API.
        """
        from lib.testtool import RunCard as RC
        cls.runcard = None
        try:
            cls.runcard = RC.Runcard(**runcard_params['initialization'])
            cls.runcard.start_test(**runcard_params['start_params'])
            logger.LogEvt("[RunCard] Started")
        except Exception as exc:
            logger.LogEvt(f"[RunCard] Init failed — {exc} (continuing)")
            cls.runcard = None

    @classmethod
    def _teardown_runcard(cls, session) -> None:
        """
        End RunCard with PASS or FAIL based on ``session.testsfailed``.
        No-op when ``cls.runcard`` is ``None``.

        Args:
            session: The pytest ``Session`` object (``request.session``).
        """
        if getattr(cls, 'runcard', None) is None:
            return
        from lib.testtool import RunCard as RC
        try:
            if session.testsfailed > 0:
                cls.runcard.end_test(
                    RC.TestResult.FAIL.value,
                    f"{session.testsfailed} test(s) failed",
                )
            else:
                cls.runcard.end_test(RC.TestResult.PASS.value)
        except Exception as exc:
            logger.LogErr(f"[RunCard] end_test failed — {exc}")

    @classmethod
    def _teardown_reboot_manager(cls) -> None:
        """
        Clean up RebootManager state file and auto-run BAT (best-effort).
        Swallows all exceptions so teardown always completes.
        """
        try:
            cls.reboot_mgr.cleanup()
        except Exception as exc:
            logger.LogEvt(f"[TEARDOWN] RebootManager cleanup failed — {exc} (continuing)")
    @classmethod
    def _revert_osconfig(
        cls,
        osconfig_yaml: "Path",
        controller: "object | None",
        log,
    ) -> None:
        """
        Revert OsConfig changes safely across reboots.

        Pre-reboot path:  *controller* is still alive → call ``revert_all()`` directly.
        Post-reboot path: *controller* is ``None`` → rebuild profile from *osconfig_yaml*
                          and load the snapshot that was persisted to disk before the
                          reboot, then call ``revert_all()``.  No-op when no snapshot
                          exists on disk.

        Args:
            osconfig_yaml: Path to the test case’s ``Config/osconfig.yaml``.
            controller:    The ``OsConfigController`` cached at apply time
                           (``cls._osconfig_controller``).  Pass ``None`` after a reboot.
            log:           A logger instance (e.g. ``get_module_logger(__name__)``).
        """
        # Lazy imports so BaseTestCase never hard-depends on osconfig.
        from lib.testtool.osconfig import OsConfigController
        from lib.testtool.osconfig.state_manager import OsConfigStateManager
        from lib.testtool.osconfig.profile_loader import load_profile

        if controller is not None:
            try:
                log.info("[TEARDOWN] Reverting OsConfig changes (pre-reboot path)...")
                controller.revert_all()
                log.info("[TEARDOWN] OsConfig reverted successfully")
            except Exception as exc:
                log.warning(f"[TEARDOWN] OsConfig revert failed \u2014 {exc} (continuing)")
        else:
            state_mgr = OsConfigStateManager()
            if state_mgr.exists():
                try:
                    log.info("[TEARDOWN] Post-reboot OsConfig revert \u2014 loading snapshot from disk")
                    profile = load_profile(osconfig_yaml)
                    ctrl = OsConfigController(profile=profile, state_manager=state_mgr)
                    ctrl.revert_all()
                    log.info("[TEARDOWN] OsConfig reverted successfully (post-reboot)")
                except Exception as exc:
                    log.warning(f"[TEARDOWN] OsConfig post-reboot revert failed \u2014 {exc} (continuing)")
            else:
                log.info("[TEARDOWN] No OsConfig snapshot on disk \u2014 skipping revert")

    @classmethod
    def _build_auto_login_cfg(cls, profile) -> dict:
        """
        Build the auto_login_config dict for RebootManager from an OsConfigProfile.
        Returns an empty dict when auto admin logon is not enabled in the profile.

        Args:
            profile: An OsConfigProfile object (from profile_loader.load_profile).
        """
        if not getattr(profile, 'enable_auto_admin_logon', False):
            return {}
        import getpass
        return {
            "auto_login_username": profile.auto_login_username or getpass.getuser(),
            "auto_login_password": (
                profile.auto_login_password
                or os.getenv("SSD_TESTKIT_AUTO_LOGIN_PASSWORD", "")
            ),
            "auto_login_domain": profile.auto_login_domain or ".",
        }

    @classmethod
    def _resolve_log_path(cls, env_var: str, subdir: str, test_dir: "Path") -> str:
        """
        Resolve the log directory from an environment variable or the test directory.
        Creates the directory and returns the resolved path as a string.

        Args:
            env_var:  Environment variable name to check (e.g. ``"ADK_LOG_DIR"``).
            subdir:   Sub-directory appended to the env-var path or to
                      ``test_dir / "testlog"`` when the variable is unset.
            test_dir: Fallback base path (as returned by _setup_working_directory).
        """
        base = os.getenv(env_var)
        resolved = str(Path(base) / subdir) if base else str(test_dir / "testlog" / subdir)
        Path(resolved).mkdir(parents=True, exist_ok=True)
        return resolved

    @classmethod
    def _standard_teardown(
        cls,
        session,
        osconfig_yaml: "Path | None" = None,
        osconfig_controller: "object | None" = None,
        log=None,
    ) -> None:
        """
        Standard fixture teardown shared across test cases.

        Executes in order: _teardown_runcard, _revert_osconfig (when
        osconfig_yaml or osconfig_controller is provided),
        _teardown_reboot_manager, write_session_footer, os.chdir.

        Args:
            session:             pytest Session object (``request.session``).
            osconfig_yaml:       Path to Config/osconfig.yaml.  Pass ``None``
                                 to skip osconfig revert.
            osconfig_controller: Live OsConfigController or ``None``
                                 (post-reboot / not applied).
            log:                 Logger instance; falls back to the module
                                 logger when omitted.
        """
        cls._teardown_runcard(session)
        if osconfig_yaml is not None or osconfig_controller is not None:
            _log = log if log is not None else logger
            cls._revert_osconfig(osconfig_yaml, osconfig_controller, _log)
        cls._teardown_reboot_manager()
        write_session_footer(cls.__name__)
        os.chdir(cls.original_cwd)

    @staticmethod
    def _cleanup_testlog_directory():
        """
        Clean up entire testlog directory and recreate it empty.
        
        This is a framework-level utility that automatically runs before test execution.
        Removes all files and subdirectories in testlog/ and creates a fresh empty directory.
        """
        testlog_path = Path('./testlog')
        if testlog_path.exists():
            logger.LogEvt(f"[Framework] Cleaning testlog directory: {testlog_path.absolute()}")
            shutil.rmtree(testlog_path)
            logger.LogEvt("[Framework] testlog directory cleaned")
        
        # Recreate empty testlog directory
        testlog_path.mkdir(parents=True, exist_ok=True)
        logger.LogEvt(f"[Framework] Created clean testlog directory: {testlog_path.absolute()}")
    
    def get_config(self, key, default=None):
        """Read configuration"""
        import json
        try:
            with open("./Config/Config.json", 'r') as f:
                config = json.load(f)
                return config.get(key, default)
        except:
            return default
    
    def log(self, message):
        """Unified logging output"""
        logger.LogEvt(f"[LOG] {message}")
    
    def log_info(self, message):
        """Log informational message"""
        logger.LogEvt(f"[INFO] {message}")
    
    def log_error(self, message):
        """Log error message"""
        logger.LogErr(f"[ERROR] {message}")
    
    def log_step(self, step_number, description):
        """Log a test step"""
        logger.LogEvt("=" * 60)
        logger.LogEvt(f"[STEP {step_number}] {description}")
        logger.LogEvt("=" * 60)
    
    def log_result(self, passed, message):
        """Log test result"""
        if passed:
            logger.LogEvt(f"✓ [PASS] {message}")
        else:
            logger.LogErr(f"✗ [FAIL] {message}")
    
    def log_section(self, title):
        """Log a test section"""
        logger.LogEvt("")
        logger.LogEvt("=" * 60)
        logger.LogEvt(f"  {title}")
        logger.LogEvt("=" * 60)
        logger.LogEvt("")
