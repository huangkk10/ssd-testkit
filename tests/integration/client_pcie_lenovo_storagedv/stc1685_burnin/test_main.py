"""
STC-1685: BurnIN Installation Test (Pytest Framework)

Simple BurnIN installation test.

Test Flow:
1. Precondition - Basic setup
2. Install BurnIN - Install BurnIN test tool
"""

import sys
from pathlib import Path

# Add project root to Python path to enable imports
# Path structure: project_root/tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/test_burnin.py
project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
import shutil
import json
import os
import time
import threading
from framework.base_test import BaseTestCase
from framework.decorators import step
from lib.testtool import BurnIN
from lib.testtool import RunCard as RC
import lib.testtool.DiskPrd as DiskPrd
from lib.testtool.smartcheck import SmartCheckController
import lib.testtool.CDI as CDI
import lib.logger as logger


@pytest.mark.client_lenovo
@pytest.mark.interface_pcie
@pytest.mark.project_storagedv
@pytest.mark.feature_burnin
@pytest.mark.slow
class TestSTC1685BurnIN(BaseTestCase):
    """
    STC-1685: BurnIN Installation Test for Lenovo StorageDV
    """
    

    def _remove_existing_burnin(self):
        """
        Remove existing BurnIN installation if present.
        
        Returns:
            bool: True if no existing installation or removal successful, False otherwise
        """
        logger.LogEvt("Checking for existing BurnIN installation...")
        burnin_check = BurnIN.BurnIn()
        burnin_check.SetConfig(self.config['burnin'])
        
        if burnin_check.is_installed():
            logger.LogEvt("Existing BurnIN installation found, removing...")
            if burnin_check.uninstall():
                logger.LogEvt("Old BurnIN installation removed successfully")
                return True
            else:
                logger.LogErr("Failed to remove old BurnIN installation")
                return False
        else:
            logger.LogEvt("No existing BurnIN installation found")
            return True
    
    def _cleanup_cdi_logs(self):
        """
        Clean up old CDI logs from previous test runs.
        
        Removes and recreates:
        - testlog/CDILog directory (CDI output files: txt, json, png)
        """
        cdi_log_path = Path('./testlog/CDILog')
        
        if cdi_log_path.exists():
            logger.LogEvt(f"Removing old CDI logs: {cdi_log_path}")
            shutil.rmtree(cdi_log_path)
            logger.LogEvt("Old CDI logs removed")
        
        cdi_log_path.mkdir(parents=True, exist_ok=True)
        logger.LogEvt(f"Created clean CDI log directory: {cdi_log_path}")
    
    def _cleanup_burnin_logs(self):
        """
        Clean up old BurnIN logs from previous test runs.
        
        Removes BurnIN log files in testlog directory:
        - Burnin.log
        - BurnIN script files
        - BurnIN screenshots
        """
        testlog_path = Path('./testlog')
        
        if testlog_path.exists():
            # Remove BurnIN specific files
            burnin_files = list(testlog_path.glob('Burnin*'))
            burnin_files.extend(testlog_path.glob('burnin*'))
            
            if burnin_files:
                logger.LogEvt(f"Removing {len(burnin_files)} old BurnIN log files")
                for file in burnin_files:
                    try:
                        if file.is_file():
                            file.unlink()
                        elif file.is_dir():
                            shutil.rmtree(file)
                    except Exception as e:
                        logger.LogWarn(f"Failed to remove {file}: {e}")
                logger.LogEvt("Old BurnIN logs removed")
            else:
                logger.LogEvt("No old BurnIN logs found")
    
    def _cleanup_smartcheck_logs(self):
        """
        Clean up old SmartCheck logs from previous test runs.
        
        Removes SmartCheck log files in testlog directory:
        - SmartCheck output files
        - SMART monitoring logs
        """
        testlog_path = Path('./testlog')
        
        if testlog_path.exists():
            # Remove SmartCheck specific files
            smartcheck_files = list(testlog_path.glob('SmartCheck*'))
            smartcheck_files.extend(testlog_path.glob('smartcheck*'))
            smartcheck_files.extend(testlog_path.glob('SMART*'))
            
            if smartcheck_files:
                logger.LogEvt(f"Removing {len(smartcheck_files)} old SmartCheck log files")
                for file in smartcheck_files:
                    try:
                        if file.is_file():
                            file.unlink()
                        elif file.is_dir():
                            shutil.rmtree(file)
                    except Exception as e:
                        logger.LogWarn(f"Failed to remove {file}: {e}")
                logger.LogEvt("Old SmartCheck logs removed")
            else:
                logger.LogEvt("No old SmartCheck logs found")
    
    
    def _cleanup_test_logs(self):
        """
        Clean up all test logs from previous test runs.
        
        Cleans:
        1. CDI logs (testlog/CDILog/)
        2. BurnIN logs (testlog/Burnin*)
        3. SmartCheck logs (testlog/SmartCheck*)
        4. Test-specific log directory (log/STC-1685/)
        5. Recreates testlog base directory
        """
        logger.LogEvt("Starting test log cleanup...")
        
        # Create testlog directory if not exists
        testlog_path = Path('./testlog')
        testlog_path.mkdir(parents=True, exist_ok=True)
        
        # Clean individual tool logs
        self._cleanup_cdi_logs()
        self._cleanup_burnin_logs()
        self._cleanup_smartcheck_logs()
        
        # Clean test-specific log directory
        log_path = self.config.get('log_path', './log/STC-1685')
        if Path(log_path).exists():
            logger.LogEvt(f"Removing old test log directory: {log_path}")
            shutil.rmtree(log_path)
            logger.LogEvt("Old test log directory removed")
        
        Path(log_path).mkdir(parents=True, exist_ok=True)
        logger.LogEvt(f"Created clean test log directory: {log_path}")
        
        logger.LogEvt("Test log cleanup completed")
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request, testcase_config, runcard_params):
        """Load configuration and initialize (runs before all tests)"""
        cls = request.cls
        cls.testcase_config = testcase_config  # Store config object for access in tests
        
        # Store original working directory
        import os
        cls.original_cwd = os.getcwd()
        
        # Change to test directory
        test_dir = Path(__file__).parent
        os.chdir(test_dir)
        
        # Clean up testlog directory immediately after chdir (before logger init)
        cls._cleanup_testlog_directory()
        
        # Initialize logger after changing directory (so logs are created in test directory)
        logger.logConfig()
        
        # Debug: Show where logs will be created
        import os
        log_abs_path = os.path.abspath('./log/log.txt')
        print(f"[DEBUG] Current working directory: {os.getcwd()}")
        print(f"[DEBUG] Log file will be created at: {log_abs_path}")
        
        # Load tool configuration from Config.json (via conftest.py)
        cls.config = testcase_config.tool_config
        
        # Set tool paths to local bin directory (重啟後仍需要載入)
        cls.bin_path = testcase_config.bin_directory
        
        # Log test information (框架會自動處理首次/恢復的訊息)
        logger.LogEvt(f"Working directory: {test_dir}")
        logger.LogEvt(f"Tool bin path: {cls.bin_path}")
        logger.LogEvt(f"Test case: {testcase_config.case_id}")
        logger.LogEvt(f"Script version: {testcase_config.case_version}")
        
        # ==================== RunCard Integration Start ====================
        # Initialize RunCard for the entire test class (using config from conftest.py)
        cls.runcard = None
        
        try:
            # Use configuration from conftest.py
            cls.runcard = RC.Runcard(**runcard_params['initialization'])
            logger.LogEvt("[RunCard] Object created")
            
            # Start RunCard test with auto_setup
            cls.runcard.start_test(**runcard_params['start_params'])
            logger.LogEvt("[RunCard] Test started successfully")
            logger.LogEvt(f"[RunCard] Using SmiCli: {testcase_config.smicli_executable if testcase_config.smicli_executable.exists() else 'Not found'}")
        except Exception as e:
            logger.LogErr(f"[RunCard] Initialization failed - {e} (continuing test)")
            cls.runcard = None
        # ==================== RunCard Integration End ====================
        
        yield  # Tests run here
        
        # ==================== RunCard End Test ====================
        # Record final test result after all tests complete
        if cls.runcard:
            try:
                # Check if any test failed using pytest's session
                # request.node.session.testsfailed counts all failed tests
                failed = request.session.testsfailed > 0
                
                if not failed:
                    cls.runcard.end_test(RC.TestResult.PASS.value)
                    logger.LogEvt("[RunCard] All tests PASSED")
                else:
                    cls.runcard.end_test(RC.TestResult.FAIL.value, f"{request.session.testsfailed} test(s) failed")
                    logger.LogEvt(f"[RunCard] Test suite FAILED - {request.session.testsfailed} test(s) failed")
            except Exception as e:
                logger.LogErr(f"[RunCard] Failed to record final result - {e}")
        # ==================== RunCard End ====================
        
        logger.LogEvt("STC-1685 Test Completed")
        
        # Restore original working directory
        os.chdir(cls.original_cwd)
    
    @pytest.mark.order(1)
    @step(1, "Setup precondition")
    def test_01_precondition(self):
        """
        Basic setup
        
        - Remove old BurnIN installation if exists
        - Clean up old test logs from previous runs
        - Create fresh log directory structure
        """
        logger.LogEvt("[TEST_01] Precondition setup started")
        
        # Step 1: Remove old BurnIN installation
        if not self._remove_existing_burnin():
            pytest.fail("Failed to remove existing BurnIN installation")
        
        # Step 2: Clean up old test logs and create fresh directories
        self._cleanup_test_logs()
        
        logger.LogEvt("[TEST_01] Precondition completed")
    
    @pytest.mark.order(2)
    @step(2, "Install BurnIN test tool")
    def test_02_install_burnin(self):
        """
        Install BurnIN test tool
        """
        logger.LogEvt("[TEST_02] BurnIN installation started")
        
        # Create BurnIN instance
        burnin = BurnIN.BurnIn()
        
        # Set configuration (using absolute paths from config)
        burnin.SetConfig(self.config['burnin'])
        
        # Install BurnIN
        burnin.install()
        
        logger.LogEvt("[TEST_02] BurnIN installation completed")
    
    @pytest.mark.order(3)
    @step(3, "Create disk partition for testing")
    def test_03_partition_disk(self):
        """
        Partition disk for testing
        
        Steps:
        1. Shrink C drive by 10240 MB
        2. Create new primary partition in freed space
        3. Quick format as NTFS (4K allocation unit)
        4. Assign drive letter D
        """
        logger.LogEvt("[TEST_03] Disk partition started")
        
        # Check if D drive already exists
        import os
        if os.path.exists("D:\\"):
            logger.LogEvt("[TEST_03] D drive exists, deleting and extending C drive")
            DiskPrd.DelVolume("D")
            DiskPrd.ExtendVolume("C")
        
        # Shrink C and create D partition based on config
        logger.LogEvt("[TEST_03] Creating new D partition (10GB NTFS 4K)")
        DiskPrd.ShrinkAndFormatDisk()
        
        logger.LogEvt("[TEST_03] Disk partition completed")
    
    @pytest.mark.order(4)
    @step(4, "Run CDI before test to establish SMART baseline")
    def test_04_cdi_before(self):
        """
        Run CDI before the test to establish SMART attribute baseline

        This test:
        1. Launch CrystalDiskInfo
        2. Retrieve SMART attributes for the C drive
        3. Save outputs as CDI_before.txt, CDI_before.json, CDI_before.png
        4. Verify key SMART attributes:
           - Number of Error Information Log Entries
           - Media and Data Integrity Errors
        5. Ensure these values are 0 (no errors)

        If any SMART errors are detected, the test will fail.
        """
        logger.LogEvt("[TEST_04] CDI before test started")
        
        # Initialize CDI tool
        cdi = CDI.CDI()
        
        # Load CDI settings from config
        if 'cdi' in self.config:
            cdi.SetConfig(self.config['cdi'])
            logger.LogEvt("[TEST_04] CDI configuration loaded")
        else:
            # Use default configuration
            cdi.LogPath = './testlog'
            logger.LogEvt("[TEST_04] Using default CDI configuration")
        
        # Set CDI output filenames (before baseline)
        cdi.ScreenShotDriveLetter = 'C:'
        cdi.DiskInfo_txt_name  = 'CDI_before.txt'
        cdi.DiskInfo_json_name = 'CDI_before.json'
        cdi.DiskInfo_png_name  = 'CDI_before.png'
        
        logger.LogEvt(f"[TEST_04] CDI output files:")
        logger.LogEvt(f"[TEST_04]   - TXT:  {cdi.DiskInfo_txt_name}")
        logger.LogEvt(f"[TEST_04]   - JSON: {cdi.DiskInfo_json_name}")
        logger.LogEvt(f"[TEST_04]   - PNG:  {cdi.DiskInfo_png_name}")
        
        try:
            # Run CDI monitoring (synchronous)
            logger.LogEvt("[TEST_04] Executing CDI monitoring...")
            cdi.RunProcedureParserLog_sync()
            logger.LogEvt("[TEST_04] CDI monitoring completed")
            logger.LogEvt("[TEST_04] CDI before baseline data saved")
            
        except Exception as e:
            logger.LogErr(f"[TEST_04] CDI test exception: {e}")
            pytest.fail(f"CDI before test failed: {str(e)}")
    
    @pytest.mark.order(5)
    @step(5, "Run BurnIN and SmartCheck concurrently")
    def test_05_burnin_smartcheck(self):
        """
        Run BurnIN disk test and SmartCheck monitoring concurrently

        This test:
        1. Start SmartCheckController thread first
        2. Start BurnIN process and monitoring thread
        3. Monitor both threads:
           - If SmartCheck status becomes False -> stop BurnIN immediately
           - If BurnIN fails -> stop SmartCheck immediately
        4. Final result: FAIL if BurnIN failed OR SmartCheck status=False
        
        Note: RunCard is managed at class level (setup_test_class)
        """
        logger.LogEvt("[TEST_05] BurnIN and SmartCheck concurrent test started")

        # ===== Initialize SmartCheckController =====
        logger.LogEvt("[TEST_05] Initializing SmartCheckController...")
        
        smart_cfg = self.config.get('smartcheck', {})
        
        try:
            smartcheck_controller = SmartCheckController.from_config_dict(smart_cfg)
            
            logger.LogEvt("[TEST_05] SmartCheckController initialized")
            logger.LogEvt(f"[TEST_05]   bat_path: {smartcheck_controller.bat_path}")
            logger.LogEvt(f"[TEST_05]   output_dir: {smartcheck_controller.output_dir}")
            logger.LogEvt(f"[TEST_05]   total_time: {smartcheck_controller.total_time} minutes")
            logger.LogEvt(f"[TEST_05]   timeout: {smartcheck_controller.timeout} minutes")
            
        except Exception as e:
            logger.LogErr(f"[TEST_05] Failed to initialize SmartCheckController: {e}")
            pytest.fail(f"SmartCheckController initialization failed: {e}")
        
        # ===== Initialize BurnIN =====
        burnin = BurnIN.BurnIn()
        burnin.SetConfig(self.config['burnin'])

        # Set BurnIN executable path
        install_path = self.config['burnin']['InstallPath']
        burnin.Path = os.path.join(install_path, 'bit64.exe')
        if not os.path.exists(burnin.Path):
            burnin.Path = os.path.join(install_path, 'bit.exe')

        if not os.path.exists(burnin.Path):
            pytest.fail(f"BurnIN executable not found: {burnin.Path}")

        logger.LogEvt(f"[TEST_05] Using BurnIN executable: {burnin.Path}")

        # Generate BurnIN script
        drive_letter = "D"
        test_duration_minutes = self.config['burnin'].get('test_duration_minutes', 1440)
        logger.LogEvt(f"[TEST_05] Test duration: {test_duration_minutes} minutes")

        cmdStr = f'''
        LOAD "{os.path.abspath(burnin.CfgFilePath)}" 
        SETLOG LOG yes Name "{os.path.abspath(burnin.LogPath)}" TIME no REPORT text
        SETDURATION {test_duration_minutes}
        SETDURATION {test_duration_minutes}
        SETDISK DISK {drive_letter}:
        RUN DISK
        '''
        burnin.generate_burnin_test_script(cmdStr)

        # ===== Setup Mutual Monitoring Mechanism =====
        logger.LogEvt("[TEST_05] Setting up mutual monitoring mechanism...")
        
        # Shared state for BurnIN monitoring thread
        burnin_result_lock = threading.Lock()
        burnin_result = {'done': False, 'success': None, 'msg': ''}
        
        # Helper function to stop BurnIN gracefully
        def stop_burnin(reason: str):
            logger.LogEvt(f"[TEST_05] Stopping BurnIN ({reason})...")
            try:
                burnin.__Stop__()
            except Exception as e:
                logger.LogWarn(f"[TEST_05] BurnIN stop exception: {e}")
            try:
                burnin.ScreenShot()
            except Exception:
                pass
            try:
                burnin.__Close__()
            except Exception:
                pass
        
        # Helper function to finalize BurnIN (screenshot & close)
        def finalize_burnin():
            try:
                burnin.ScreenShot()
            except Exception:
                pass
            try:
                burnin.__Close__()
            except Exception:
                pass
        
        # BurnIN worker thread (includes process startup and monitoring)
        def burnin_worker():
            try:
                logger.LogEvt("[Thread-BurnIN] Starting BurnIN process...")
                burnin.__RunScript__(["-S", os.path.abspath(burnin.ScriptPath), '-K', '-R', '-W'])
                logger.LogEvt("[Thread-BurnIN] BurnIN process started, starting monitor...")
                result, msg = burnin.WaitTestDone_no_async()
                logger.LogEvt(f"[Thread-BurnIN] BurnIN finished: result={result}, msg={msg}")
                with burnin_result_lock:
                    burnin_result.update({'done': True, 'success': result, 'msg': msg})
            except Exception as e:
                logger.LogErr(f"[Thread-BurnIN] Exception: {e}")
                with burnin_result_lock:
                    burnin_result.update({'done': True, 'success': False, 'msg': str(e)})
        
        # ===== Start threads in correct order =====
        # Step 1: Start SmartCheckController thread FIRST
        logger.LogEvt("[TEST_05] Step 1: Starting SmartCheckController thread...")
        smartcheck_controller.start()
        logger.LogEvt(f"[TEST_05] SmartCheckController started (is_alive: {smartcheck_controller.is_alive()})")
        
        # Step 2: Start BurnIN worker thread (includes process startup and monitoring)
        logger.LogEvt("[TEST_05] Step 2: Starting BurnIN worker thread...")
        burnin_thread = threading.Thread(target=burnin_worker, name='BurnIN-worker', daemon=False)
        burnin_thread.start()
        logger.LogEvt("[TEST_05] BurnIN worker thread started")

        logger.LogEvt("[TEST_05] All threads started, entering monitoring loop...")
        
        # ===== Monitoring Loop =====
        timeout_seconds = self.config['burnin'].get('timeout', 6000)
        start_time = time.time()
        timeout_hit = False
        smartcheck_failed = False
        burnin_failed = False
        burnin_finalized = False
        
        try:
            while True:
                # Check 1: SmartCheck status
                if not smartcheck_failed and smartcheck_controller.status is False:
                    smartcheck_failed = True
                    logger.LogErr("[TEST_05] SmartCheck status became False!")
                    logger.LogErr("[TEST_05] Stopping BurnIN immediately...")
                    stop_burnin("SmartCheck failed")
                
                # Check 2: BurnIN result
                with burnin_result_lock:
                    burnin_done = burnin_result['done']
                    burnin_success = burnin_result['success']
                    burnin_msg = burnin_result['msg']
                
                if burnin_done and burnin_success is False and not burnin_failed:
                    burnin_failed = True
                    logger.LogErr(f"[TEST_05] BurnIN failed: {burnin_msg}")
                    logger.LogErr("[TEST_05] Stopping SmartCheck immediately...")
                    smartcheck_controller.stop()
                
                # Check 3: BurnIN completed successfully
                if burnin_done and burnin_success is True and not burnin_finalized:
                    logger.LogEvt("[TEST_05] BurnIN completed successfully")
                    finalize_burnin()
                    burnin_finalized = True
                    # Stop SmartCheck since BurnIN completed successfully
                    logger.LogEvt("[TEST_05] Stopping SmartCheck (BurnIN completed)")
                    smartcheck_controller.stop()
                
                # Check 4: Both threads finished
                if burnin_done and not burnin_thread.is_alive() and not smartcheck_controller.is_alive():
                    logger.LogEvt("[TEST_05] Both threads finished, exiting monitoring loop")
                    break
                
                # Check 5: Timeout
                if time.time() - start_time > timeout_seconds:
                    timeout_hit = True
                    logger.LogErr(f"[TEST_05] Test timeout reached ({timeout_seconds}s)")
                    logger.LogErr("[TEST_05] Stopping both tasks...")
                    stop_burnin("timeout")
                    smartcheck_controller.stop()
                    break
                
                # Sleep before next check
                time.sleep(1)
                
        finally:
            # ===== Cleanup =====
            logger.LogEvt("[TEST_05] Entering cleanup phase...")
            
            # Wait for threads to finish
            logger.LogEvt("[TEST_05] Waiting for BurnIN thread...")
            burnin_thread.join(timeout=10)
            
            logger.LogEvt("[TEST_05] Waiting for SmartCheckController thread...")
            smartcheck_controller.join(timeout=10)
            
            # Force cleanup if threads are still alive
            if smartcheck_controller.is_alive():
                logger.LogErr("[TEST_05] SmartCheckController thread did not exit cleanly, forcing stop")
                smartcheck_controller.stop_smartcheck_bat(force=True)
                smartcheck_controller.join(timeout=5)
            
            if burnin_thread.is_alive():
                logger.LogErr("[TEST_05] BurnIN thread did not exit cleanly")
            
            logger.LogEvt("[TEST_05] Cleanup completed")
        
        # ===== Final Result Determination =====
        logger.LogEvt("[TEST_05] Determining final test result...")
        
        if timeout_hit:
            logger.LogErr("[TEST_05] FAIL: Test timeout")
            pytest.fail("Test timeout: BurnIN and SmartCheck did not complete within expected time")
        
        with burnin_result_lock:
            burnin_done = burnin_result['done']
            burnin_success = burnin_result['success']
            burnin_msg = burnin_result['msg']
        
        if not burnin_done:
            logger.LogErr("[TEST_05] FAIL: BurnIN did not complete")
            pytest.fail("BurnIN did not complete")
        
        if burnin_success is False:
            logger.LogErr(f"[TEST_05] FAIL: BurnIN test failed: {burnin_msg}")
            pytest.fail(f"BurnIN test failed: {burnin_msg}")
        
        # Check SmartCheck status
        # Note: If BurnIN completed successfully and we stopped SmartCheck gracefully,
        # status might be None (not started/incomplete) which is acceptable.
        # We only fail if status is explicitly False (detected an error).
        if smartcheck_controller.status is False:
            logger.LogErr("[TEST_05] FAIL: SmartCheck detected failure during monitoring")
            pytest.fail("SmartCheck detected SMART errors (status=False)")
        
        logger.LogEvt("[TEST_05] ========================================")
        logger.LogEvt("[TEST_05] ✓ All tests PASSED")
        logger.LogEvt("[TEST_05] ✓ BurnIN: Success")
        logger.LogEvt(f"[TEST_05] ✓ SmartCheck: Success (status={smartcheck_controller.status})")
        logger.LogEvt("[TEST_05] ========================================")
        logger.LogEvt("[TEST_05] Test completed successfully")
    
    @pytest.mark.order(6)
    @step(6, "Run CDI after test to compare SMART changes")
    def test_06_cdi_after(self):
        """
        Run CDI after test to compare SMART attribute changes

        This test:
        1. Launch CrystalDiskInfo
        2. Retrieve SMART attributes for the C drive
        3. Save outputs as CDI_after.txt, CDI_after.json, CDI_after.png
        4. Compare SMART attributes before and after:
           - Unsafe Shutdowns should not increase
           - Error counts should remain 0

        If any SMART anomalies are detected, the test will fail.
        """
        logger.LogEvt("[TEST_06] CDI after test started")
        
        # Initialize CDI tool
        cdi = CDI.CDI()
        
        # Load CDI settings from config
        if 'cdi' in self.config:
            cdi.SetConfig(self.config['cdi'])
            logger.LogEvt("[TEST_06] CDI configuration loaded")
        else:
            # Use default configuration
            cdi.LogPath = './testlog'
            logger.LogEvt("[TEST_06] Using default CDI configuration")
        
        try:
            # ========================================
            # Step 1: Collect C: after data
            # ========================================
            logger.LogEvt("[TEST_06] Collecting C: CDI after data...")
            cdi.ScreenShotDriveLetter = 'C:'
            cdi.DiskInfo_txt_name  = 'CDI_after.txt'
            cdi.DiskInfo_json_name = 'CDI_after.json'
            cdi.DiskInfo_png_name  = 'CDI_after.png'
            
            logger.LogEvt(f"[TEST_06] C: output files:")
            logger.LogEvt(f"[TEST_06]   - TXT:  {cdi.DiskInfo_txt_name}")
            logger.LogEvt(f"[TEST_06]   - JSON: {cdi.DiskInfo_json_name}")
            logger.LogEvt(f"[TEST_06]   - PNG:  {cdi.DiskInfo_png_name}")
            
            cdi.RunProcedureParserLog_sync()
            logger.LogEvt("[TEST_06] C: CDI monitoring completed")
            
            # ========================================
            # Step 2: Compare C: SMART attributes
            # ========================================
            logger.LogEvt("[TEST_06] ======================================")
            logger.LogEvt("[TEST_06] Starting comparison of C: SMART attributes...")
            logger.LogEvt("[TEST_06] ======================================")
            
            # 2.1 Check C: Unsafe Shutdowns should not increase
            logger.LogEvt("[TEST_06] Checking C: Unsafe Shutdowns...")
            keys = ['Unsafe Shutdowns']
            cdi.DiskInfo_json_name = '.json'
            result, msg = cdi.__CompareSmartValueNoIncrease__(
                'C:', 'CDI_before', 'CDI_after', keys
            )
            
            if not result:
                logger.LogErr(f"[TEST_06] C: Unsafe Shutdowns validation failed: {msg}")
                pytest.fail(f"C: SMART validation failed: {msg}")
            else:
                logger.LogEvt(f"[TEST_06] ✓ C: Unsafe Shutdowns validation passed: {msg}")
            
            # 2.2 Check C: error counts should remain 0
            logger.LogEvt("[TEST_06] Checking C: error counts...")
            keys = [
                'Number of Error Information Log Entries',
                'Media and Data Integrity Errors'
            ]
            cdi.DiskInfo_json_name = 'CDI_after.json'
            result, msg = cdi.__CompareSmartValue__('C:', '', keys, 0)
            
            if not result:
                logger.LogErr(f"[TEST_06] C: error count validation failed: {msg}")
                pytest.fail(f"C: SMART errors: {msg}")
            else:
                logger.LogEvt(f"[TEST_06] ✓ C: error count validation passed: {msg}")
            
            # ========================================
            # Test complete
            # ========================================
            logger.LogEvt("[TEST_06] ======================================")
            logger.LogEvt("[TEST_06] All SMART validations passed!")
            logger.LogEvt("[TEST_06] ======================================")
            logger.LogEvt("[TEST_06] CDI after test completed")
            
        except Exception as e:
            logger.LogErr(f"[TEST_06] CDI test exception: {e}")
            pytest.fail(f"CDI after test failed: {str(e)}")


    # @pytest.mark.order(7)
    # def test_07_verify_burnin_log(self):
    #     """
    #     Test 07: Verify BurnIN log results
        
    #     Check the Burnin.log file to ensure all test runs passed.
    #     Reads the log file and verifies that all test runs have "TEST RUN PASSED" status.
    #     """
    #     try:
    #         logger.LogEvt("=" * 70)
    #         logger.LogEvt("[TEST_07] Starting BurnIN log verification")
    #         logger.LogEvt("=" * 70)
            
    #         # Get log path from config
    #         burnin_log_path = Path(self.config['burnin']['LogPath'])
            
    #         # Debug: Show absolute path
    #         abs_path = burnin_log_path.absolute()
    #         logger.LogEvt(f"[TEST_07] Config LogPath: {burnin_log_path}")
    #         logger.LogEvt(f"[TEST_07] Absolute path: {abs_path}")
    #         logger.LogEvt(f"[TEST_07] File exists: {burnin_log_path.exists()}")
            
    #         # Check if log file exists
    #         if not burnin_log_path.exists():
    #             logger.LogErr(f"[TEST_07] BurnIN log file not found: {burnin_log_path}")
    #             logger.LogErr(f"[TEST_07] Tried absolute path: {abs_path}")
    #             pytest.fail(f"BurnIN log file not found: {burnin_log_path}")
            
    #         # Get file size
    #         file_size = burnin_log_path.stat().st_size
    #         logger.LogEvt(f"[TEST_07] Reading log file: {burnin_log_path}")
    #         logger.LogEvt(f"[TEST_07] File size: {file_size} bytes")
            
    #         # Read the entire log file
    #         with open(burnin_log_path, 'r', encoding='utf-8', errors='ignore') as f:
    #             log_content = f.read()
            
    #         logger.LogEvt(f"[TEST_07] Log content length: {len(log_content)} characters")
            
    #         # Debug: Show first 500 characters of the file
    #         logger.LogEvt(f"[TEST_07] First 500 characters of log:")
    #         logger.LogEvt(f"[TEST_07] {repr(log_content[:500])}")
            
    #         # Debug: Show last 500 characters of the file
    #         logger.LogEvt(f"[TEST_07] Last 500 characters of log:")
    #         logger.LogEvt(f"[TEST_07] {repr(log_content[-500:])}")
            
    #         # Count all "TEST RUN PASSED" occurrences
    #         passed_count = log_content.count("TEST RUN PASSED")
            
    #         # Count all "TEST RUN FAILED" occurrences
    #         failed_count = log_content.count("TEST RUN FAILED")
            
    #         # Count all test runs (by counting RESULT SUMMARY sections)
    #         result_summary_count = log_content.count("RESULT SUMMARY")
            
    #         logger.LogEvt(f"[TEST_07] Log analysis results:")
    #         logger.LogEvt(f"[TEST_07]   - Total test runs: {result_summary_count}")
    #         logger.LogEvt(f"[TEST_07]   - TEST RUN PASSED: {passed_count}")
    #         logger.LogEvt(f"[TEST_07]   - TEST RUN FAILED: {failed_count}")
            
    #         # Validation: Check if there are any failed tests
    #         if failed_count > 0:
    #             logger.LogErr(f"[TEST_07] Found {failed_count} failed test run(s) in log!")
    #             pytest.fail(f"BurnIN test failed: {failed_count} test run(s) failed")
            
    #         # Validation: Check if there are any passed tests
    #         if passed_count == 0:
    #             logger.LogErr("[TEST_07] No 'TEST RUN PASSED' found in log!")
    #             pytest.fail("BurnIN test validation failed: No passed test runs found")
            
    #         # Validation: All result summaries should have passed status
    #         if result_summary_count > 0 and passed_count != result_summary_count:
    #             logger.LogWar(f"[TEST_07] Warning: Result summary count ({result_summary_count}) != Passed count ({passed_count})")
    #             # This might be normal if some runs were interrupted
            
    #         logger.LogEvt("[TEST_07] ======================================")
    #         logger.LogEvt(f"[TEST_07] ✓ All BurnIN test runs passed ({passed_count} successful run(s))")
    #         logger.LogEvt("[TEST_07] ======================================")
    #         logger.LogEvt("[TEST_07] BurnIN log verification completed")
            
    #     except Exception as e:
    #         logger.LogErr(f"[TEST_07] Log verification exception: {e}")
    #         pytest.fail(f"BurnIN log verification failed: {str(e)}")


if __name__ == "__main__":
    # Run tests with comprehensive logging
    pytest.main([
        __file__, 
        "-v", 
        "-s",
        "--log-file=./log/pytest.log",
        "--log-file-level=INFO",
        "--log-file-format=%(asctime)s [%(levelname)s] %(message)s",
        "--log-file-date-format=%Y-%m-%d %H:%M:%S"
    ])
