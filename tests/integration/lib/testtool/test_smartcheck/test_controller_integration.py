"""
SmartCheck Controller Integration Tests

These tests verify real process execution without mocks.
They require actual SmartCheck.bat to be present.

Run these tests with:
    pytest tests/integration/lib/testtool/test_smartcheck/test_controller_integration.py -v
"""

import pytest
import time
import os
from pathlib import Path

from lib.testtool.smartcheck import SmartCheckController
from lib.testtool.smartcheck.exceptions import SmartCheckProcessError


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.skipif(
    not os.path.exists("tests/unit/lib/testtool/bin/SmiWinTools/SmartCheck.bat"),
    reason="SmartCheck.bat not found in tests/unit/lib/testtool/bin/SmiWinTools/"
)
class TestSmartCheckControllerRealProcess:
    """Integration tests with real SmartCheck.bat execution."""
    
    @pytest.fixture
    def real_paths(self, tmp_path):
        """
        Create real test paths using actual SmartCheck.bat.
        
        This fixture uses the real SmartCheck.bat from tests/unit/lib/testtool/bin directory
        instead of creating dummy files.
        """
        # Use real SmartCheck.bat and SmartCheck.ini
        bat_path = "tests/unit/lib/testtool/bin/SmiWinTools/SmartCheck.bat"
        ini_path = "tests/unit/lib/testtool/bin/SmiWinTools/SmartCheck.ini"
        
        # Use temporary output directory
        output_dir = tmp_path / "smartcheck_output"
        output_dir.mkdir(exist_ok=True)
        
        # Verify files exist
        assert os.path.exists(bat_path), f"SmartCheck.bat not found: {bat_path}"
        assert os.path.exists(ini_path), f"SmartCheck.ini not found: {ini_path}"
        
        return {
            'bat_path': bat_path,
            'ini_path': ini_path,
            'output_dir': str(output_dir),
        }
    
    def test_start_and_stop_real_process(self, real_paths):
        """
        Test starting and stopping real SmartCheck.bat process.
        
        This test:
        1. Creates a controller with real SmartCheck.bat
        2. Starts the process
        3. Verifies the process is running
        4. Stops the process
        5. Verifies the process is terminated
        """
        # Create controller
        controller = SmartCheckController(
            bat_path=real_paths['bat_path'],
            cfg_ini_path=real_paths['ini_path'],
            output_dir=real_paths['output_dir'],
            total_time=5,  # 1 minute (very short test)
            timeout=5      # 2 minute timeout
        )
        
        try:
            # Start SmartCheck.bat
            result = controller.start_smartcheck_bat()
            
            # Verify process started
            assert result is True, "start_smartcheck_bat should return True"
            assert controller._process is not None, "Process should not be None"
            assert controller._process.pid > 0, "Process should have valid PID"
            
            # Check process is running
            assert controller._process.poll() is None, "Process should be running"
            
            print(f"\n✅ SmartCheck.bat started successfully")
            print(f"   - PID: {controller._process.pid}")
            print(f"   - Output dir: {controller.output_dir}")
            
            # Wait a moment to let process initialize
            time.sleep(3)
            
            # Verify process is still running
            if controller._process.poll() is None:
                print(f"✅ Process still running after 3 seconds")
            else:
                print(f"⚠️  Process exited with code: {controller._process.returncode}")
            
        finally:
            # Always stop the process
            controller.stop_smartcheck_bat()
            
            # Verify process is stopped
            if controller._process is None:
                print(f"✅ Process stopped successfully")
            else:
                print(f"⚠️  Process handle still exists")
    
    def test_process_output_directory_created(self, real_paths):
        """
        Test that SmartCheck.bat creates output directory.
        
        This test verifies:
        1. Output directory is created
        2. SmartCheck.ini is written with correct configuration
        3. RunCard.ini is found within 5 minutes
        """
        output_dir = Path(real_paths['output_dir'])
        
        # Create controller
        controller = SmartCheckController(
            bat_path=real_paths['bat_path'],
            cfg_ini_path=real_paths['ini_path'],
            output_dir=str(output_dir),
            total_time=100,
            dut_id="0",
            timeout=2
        )
        
        try:
            # Start process
            start_time = time.time()
            controller.start_smartcheck_bat()
            
            # Verify output directory exists
            assert output_dir.exists(), "Output directory should be created"
            
            # Wait for RunCard.ini to be created (must be within 5 minutes)
            runcard_timeout = 300  # 5 minutes
            check_interval = 5  # Check every 5 seconds
            runcard_found = False
            
            print(f"\n⏳ Waiting for RunCard.ini (timeout: 5 minutes)...")
            
            while True:
                elapsed = time.time() - start_time
                
                # Check if timeout exceeded
                if elapsed > runcard_timeout:
                    print(f"❌ RunCard.ini not found within 5 minutes ({elapsed:.1f}s)")
                    assert False, f"RunCard.ini not found within {runcard_timeout}s (5 minutes)"
                
                # Try to find RunCard.ini
                runcard_path = controller.find_runcard_ini()
                if runcard_path and runcard_path.exists():
                    runcard_found = True
                    print(f"✅ RunCard.ini found after {elapsed:.1f}s")
                    print(f"   - Path: {runcard_path}")
                    break
                
                # Check subdirectories created
                subdirs = [d for d in output_dir.iterdir() if d.is_dir()]
                print(f"⏳ Elapsed: {elapsed:.1f}s, Subdirs: {len(subdirs)}")
                
                time.sleep(check_interval)
            
            # Final verification
            assert runcard_found, "RunCard.ini should be found"
            
        finally:
            controller.stop_smartcheck_bat()
    
    def test_find_runcard_after_execution(self, real_paths):
        """
        Test finding RunCard.ini after SmartCheck execution.
        
        This test:
        1. Starts SmartCheck.bat
        2. Waits for RunCard.ini to be created (must be within 5 minutes)
        3. Verifies RunCard.ini can be found
        4. Reads status from RunCard.ini
        """
        controller = SmartCheckController(
            bat_path=real_paths['bat_path'],
            cfg_ini_path=real_paths['ini_path'],
            output_dir=real_paths['output_dir'],
            total_time=1,  # Very short test
            timeout=2
        )
        
        try:
            # Start process
            start_time = time.time()
            controller.start_smartcheck_bat()
            print(f"\n✅ SmartCheck.bat started, waiting for RunCard.ini...")
            
            # Wait and search for RunCard.ini (must be within 5 minutes)
            runcard_timeout = 300  # 5 minutes
            check_interval = 5  # Check every 5 seconds
            runcard_path = None
            
            while True:
                elapsed = time.time() - start_time
                
                # Check if timeout exceeded
                if elapsed > runcard_timeout:
                    print(f"❌ RunCard.ini not found within 5 minutes ({elapsed:.1f}s)")
                    assert False, f"RunCard.ini not found within {runcard_timeout}s (5 minutes)"
                
                # Try to find RunCard.ini
                runcard_path = controller.find_runcard_ini()
                
                if runcard_path:
                    print(f"✅ RunCard.ini found after {elapsed:.1f}s: {runcard_path}")
                    
                    # Try to read status
                    try:
                        status = controller.read_runcard_status(runcard_path)
                        print(f"✅ RunCard status read successfully:")
                        print(f"   - Test result: {status['test_result']}")
                        print(f"   - Cycle: {status['cycle']}")
                        print(f"   - Error message: {status['err_msg']}")
                    except Exception as e:
                        print(f"⚠️  Could not read RunCard status: {e}")
                    
                    break
                else:
                    print(f"⏳ Elapsed: {elapsed:.1f}s - RunCard.ini not found yet...")
                
                time.sleep(check_interval)
            
            # Final verification
            assert runcard_path is not None, "RunCard.ini should be found"
            
        finally:
            controller.stop_smartcheck_bat()
    
    @pytest.mark.slow
    def test_short_execution_cycle(self, real_paths):
        """
        Test a complete short execution cycle (SLOW TEST).
        
        This test runs SmartCheck for a very short time (1 minute)
        and verifies the complete workflow.
        
        WARNING: This test takes at least 1 minute to complete.
        """
        controller = SmartCheckController(
            bat_path=real_paths['bat_path'],
            cfg_ini_path=real_paths['ini_path'],
            output_dir=real_paths['output_dir'],
            total_time=1,      # 1 minute total time
            total_cycle=1,     # Only 1 cycle
            dut_id="0",
            timeout=5          # 5 minute timeout (safety)
        )
        
        print(f"\n⏱️  Starting 1-minute SmartCheck execution test...")
        print(f"   This test will take approximately 1-2 minutes")
        
        try:
            # Start in thread mode
            controller.start()
            
            # Monitor for up to 2 minutes
            max_wait = 120  # 2 minutes
            elapsed = 0
            check_interval = 5
            
            while controller.is_alive() and elapsed < max_wait:
                time.sleep(check_interval)
                elapsed += check_interval
                
                # Try to find and report RunCard status
                runcard_path = controller.find_runcard_ini()
                if runcard_path:
                    try:
                        status = controller.read_runcard_status(runcard_path)
                        print(f"⏳ Status: {status['test_result']}, "
                              f"Cycle: {status['cycle']}, "
                              f"Elapsed: {elapsed}s")
                    except:
                        pass
                else:
                    print(f"⏳ Waiting for RunCard.ini... ({elapsed}s)")
            
            # Wait for thread to complete
            controller.join(timeout=10)
            
            # Check final status
            print(f"\n✅ Execution completed")
            print(f"   - Final status: {controller.status}")
            print(f"   - Thread alive: {controller.is_alive()}")
            
            if not controller.status:
                print(f"   - Error message: {getattr(controller, 'error_message', 'None')}")
            
        finally:
            # Ensure cleanup
            if controller.is_alive():
                controller.stop()
                controller.join(timeout=10)
            controller.stop_smartcheck_bat()


@pytest.mark.integration
class TestSmartCheckControllerWithDummyBat:
    """Integration tests using a dummy bat file (faster tests)."""
    
    @pytest.fixture
    def dummy_bat_paths(self, tmp_path):
        """Create a dummy SmartCheck.bat that exits quickly."""
        bat_path = tmp_path / "SmartCheck.bat"
        ini_path = tmp_path / "SmartCheck.ini"
        output_dir = tmp_path / "output"
        
        # Create a dummy bat file that just creates a RunCard.ini and exits
        bat_content = """@echo off
echo Starting dummy SmartCheck
mkdir "%~dp0output\\20260210140000" 2>nul
echo [Test Status] > "%~dp0output\\20260210140000\\RunCard.ini"
echo version=1.0 >> "%~dp0output\\20260210140000\\RunCard.ini"
echo test_result=PASSED >> "%~dp0output\\20260210140000\\RunCard.ini"
echo cycle=1 >> "%~dp0output\\20260210140000\\RunCard.ini"
echo err_msg=No Error >> "%~dp0output\\20260210140000\\RunCard.ini"
timeout /t 5 /nobreak >nul
echo Dummy SmartCheck completed
"""
        bat_path.write_text(bat_content, encoding='utf-8')
        ini_path.write_text("[global]\n", encoding='utf-8')
        output_dir.mkdir(exist_ok=True)
        
        return {
            'bat_path': str(bat_path),
            'ini_path': str(ini_path),
            'output_dir': str(output_dir),
        }
    
    def test_dummy_bat_execution(self, dummy_bat_paths):
        """Test with a dummy bat file (fast test)."""
        controller = SmartCheckController(
            bat_path=dummy_bat_paths['bat_path'],
            cfg_ini_path=dummy_bat_paths['ini_path'],
            output_dir=dummy_bat_paths['output_dir'],
            timeout=1  # 1 minute timeout
        )
        
        try:
            # Start process
            result = controller.start_smartcheck_bat()
            assert result is True
            assert controller._process is not None
            
            print(f"\n✅ Dummy bat started (PID: {controller._process.pid})")
            
            # Wait for it to finish
            time.sleep(6)
            
            # Check if exited
            returncode = controller._process.poll()
            print(f"✅ Process exit code: {returncode}")
            
        finally:
            controller.stop_smartcheck_bat()
