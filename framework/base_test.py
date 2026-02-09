"""
Base test class — all test cases should inherit from this class.
Provides standard setup/teardown hooks and test state management.
"""
import pytest
import shutil
from pathlib import Path
from framework.reboot_manager import RebootManager
from framework.test_utils import setup_test_environment, cleanup_test_environment
import lib.logger as logger

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
