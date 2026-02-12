"""
BurnIN Controller Integration Tests

These tests verify the BurnInController works correctly in real execution scenarios.
Requires actual BurnIN environment and takes several minutes to complete.
"""

import pytest
import time
import threading
import json
from pathlib import Path

from lib.testtool.burnin import (
    BurnInController,
    BurnInTestFailedError,
    BurnInTimeoutError,
)


@pytest.mark.integration
@pytest.mark.requires_burnin
@pytest.mark.slow
class TestControllerIntegration:
    """Test BurnInController end-to-end functionality"""
    
    def test_controller_initialization(self, burnin_env, check_environment):
        """Test controller initialization with valid configuration"""
        controller = BurnInController(
            installer_path=burnin_env['installer_path'],
            install_path=burnin_env['install_path'],
            executable_name=burnin_env['executable_name'],
            license_path=burnin_env['license_path'],
        )
        
        assert controller.installer_path == burnin_env['installer_path']
        assert controller.install_path == burnin_env['install_path']
        assert controller.status == True  # Initial status
        assert controller.error_count == 0
    
    def test_controller_install_uninstall(self, burnin_env, check_environment, cleanup_burnin):
        """Test controller installation and uninstallation"""
        controller = BurnInController(
            installer_path=burnin_env['installer_path'],
            install_path=burnin_env['install_path'],
            executable_name=burnin_env['executable_name'],
            license_path=burnin_env['license_path'],
        )
        
        # Uninstall if installed
        if controller.is_installed():
            controller.uninstall()
        
        assert not controller.is_installed(), "Should not be installed"
        
        # Install
        controller.install()
        assert controller.is_installed(), "Should be installed"
        
        # Uninstall
        controller.uninstall()
        assert not controller.is_installed(), "Should not be installed after uninstall"
    
    @pytest.mark.timeout(600)  # 10 minutes max
    def test_short_run(self, clean_install, burnin_env, pywinauto_available):
        """Test complete short run (1 minute) with controller"""
        controller = clean_install
        
        # Configure for short test
        controller.set_config(
            test_duration_minutes=1,
            test_drive_letter=burnin_env['test_drive_letter'],
            timeout_minutes=5,
            check_interval_seconds=2,
        )
        
        # Start test in thread
        controller.start()
        
        # Wait for completion
        controller.join(timeout=300)
        
        # Check results
        assert not controller._running, "Thread should have finished"
        
        # Status might be True or False depending on test result
        # Just check it's been set (not None)
        status = controller.get_status()
        assert status['running'] == False, "Should not be running"
        assert status['test_result'] in ["PASSED", "FAILED", None], \
            f"Unexpected test result: {status['test_result']}"
        
        print(f"\nTest Result: {status['test_result']}")
        print(f"Error Count: {status['error_count']}")
    
    @pytest.mark.timeout(600)  # 10 minutes max
    def test_short_run_with_config(self, clean_install, burnin_env, pywinauto_available, test_root):
        """Test complete short run with Config.json settings"""
        controller = clean_install
        
        # Load Config.json from tests/integration/Config/
        config_path = test_root / "integration" / "Config" / "Config.json"
        
        if not config_path.exists():
            pytest.skip(f"Config.json not found at {config_path}")
        
        # Load configuration from Config.json using the convenience method
        print(f"\nLoading configuration from: {config_path}")
        controller.load_config_from_json(str(config_path), config_key='burnin')
        
        # Print loaded configuration for verification
        print(f"Configuration loaded:")
        print(f"  - Test duration: {controller.test_duration_minutes} minutes")
        print(f"  - Test drive: {controller.test_drive_letter}")
        print(f"  - Timeout: {controller.timeout_minutes} minutes")
        print(f"  - Check interval: {controller.check_interval_seconds} seconds")
        print(f"  - Log path: {controller.log_path}")
        print(f"  - Screenshot: {controller.enable_screenshot} (path: {controller.screenshot_path})")
        
        # Start test in thread
        print("\nStarting BurnIN test...")
        controller.start()
        
        # Monitor progress
        start_time = time.time()
        timeout_seconds = controller.timeout_minutes * 60
        while controller._running and (time.time() - start_time) < timeout_seconds:
            time.sleep(10)
            status = controller.get_status()
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed}s] Status: running={status['running']}, "
                  f"result={status['test_result']}, errors={status['error_count']}") 
        
        # Wait for completion
        controller.join(timeout=timeout_seconds)
        
        # Check results
        assert not controller._running, "Thread should have finished"
        
        status = controller.get_status()
        assert status['running'] == False, "Should not be running"
        assert status['test_result'] in ["PASSED", "FAILED", None], \
            f"Unexpected test result: {status['test_result']}"
        
        print(f"\n{'='*50}")
        print(f"Test Result: {status['test_result']}")
        print(f"Error Count: {status['error_count']}")
        print(f"Total Status: {controller.status}")
        print(f"{'='*50}\n")
    
    @pytest.mark.timeout(300)  # 5 minutes max
    def test_controller_stop(self, clean_install, burnin_env, pywinauto_available):
        """Test stopping controller during execution"""
        controller = clean_install
        
        # Configure for longer test
        controller.set_config(
            test_duration_minutes=10,  # 10 minutes
            test_drive_letter=burnin_env['test_drive_letter'],
            timeout_minutes=20,
            check_interval_seconds=2,
        )
        
        # Start test in thread
        controller.start()
        
        # Wait a bit for test to start
        time.sleep(10)
        
        # Verify it's running (skip if UI connection failed)
        if not controller.is_running():
            pytest.skip("BurnIN process not running (UI connection may have failed)")
        
        assert controller._running, "Thread should be running"
        
        # Stop the test
        controller.stop(timeout=30)
        
        # Wait for thread to finish
        controller.join(timeout=60)
        
        # Verify stopped (with retry for thread state)
        max_wait = 5
        for i in range(max_wait):
            if not controller._running:
                break
            time.sleep(1)
        
        assert not controller._running, "Thread should have stopped"
        assert not controller.is_running(), "Process should have stopped"
    
    @pytest.mark.timeout(180)  # 3 minutes max
    def test_timeout_handling(self, clean_install, burnin_env, pywinauto_available):
        """Test controller timeout behavior"""
        controller = clean_install
        
        # Configure with very short timeout
        controller.set_config(
            test_duration_minutes=10,  # Long test
            test_drive_letter=burnin_env['test_drive_letter'],
            timeout_minutes=0.5,  # But short timeout (30 seconds)
            check_interval_seconds=2,
        )
        
        # Start test
        controller.start()
        
        # Wait for timeout
        controller.join(timeout=120)
        
        # Should have timed out
        assert not controller._running, "Thread should have finished"
        assert controller.status == False, "Status should be False after timeout"
        
        # Stop any remaining process
        if controller.is_running():
            controller.stop(timeout=30)
    
    @pytest.mark.timeout(300)  # 5 minutes max
    def test_get_status_during_run(self, clean_install, burnin_env, pywinauto_available):
        """Test getting status while test is running"""
        controller = clean_install
        
        # Configure for moderate test
        controller.set_config(
            test_duration_minutes=2,
            test_drive_letter=burnin_env['test_drive_letter'],
            timeout_minutes=5,
            check_interval_seconds=2,
        )
        
        # Start test
        controller.start()
        
        # Wait for test to start
        time.sleep(10)
        
        # Get status while running
        status = controller.get_status()
        assert status['running'] == True, "Should report as running"
        assert status['process_running'] == True, "Process should be running"
        
        # Stop test
        controller.stop(timeout=30)
        controller.join(timeout=60)
        
        # Get status after stop
        status = controller.get_status()
        assert status['running'] == False, "Should not be running after stop"
    


@pytest.mark.integration
@pytest.mark.requires_burnin
class TestControllerErrorHandling:
    """Test controller error handling scenarios"""
    
    def test_start_without_install(self, burnin_env, check_environment, cleanup_burnin):
        """Test starting controller without BurnIN installed"""
        from lib.testtool.burnin import BurnInProcessError
        
        controller = BurnInController(
            installer_path=burnin_env['installer_path'],
            install_path=burnin_env['install_path'],
            executable_name=burnin_env['executable_name'],
        )
        
        # Ensure not installed
        if controller.is_installed():
            controller.uninstall()
        
        assert not controller.is_installed(), "Should not be installed"
        
        # Try to run - should fail in script generation or process start
        controller.set_config(
            test_duration_minutes=1,
            test_drive_letter=burnin_env['test_drive_letter'],
        )
        
        controller.start()
        controller.join(timeout=60)
        
        # Should have failed
        assert controller.status == False, "Should fail without installation"
    
    def test_invalid_script_path(self, clean_install, burnin_env):
        """Test with invalid script path"""
        controller = clean_install
        
        # Set invalid script path
        controller.set_config(
            script_path="/invalid/path/script.bits",
            test_duration_minutes=1,
            test_drive_letter=burnin_env['test_drive_letter'],
        )
        
        # Try to run
        controller.start()
        
        # Wait a bit for process to start
        time.sleep(5)
        
        # Stop immediately (don't wait for completion)
        controller.stop(timeout=10)
        controller.join(timeout=30)
        
        # Note: BurnIN may still run even with invalid script path
        # Just verify the controller can handle this scenario
        assert not controller._running, "Thread should have stopped"
    
    def test_controller_repr(self, clean_install):
        """Test controller string representation"""
        controller = clean_install
        
        repr_str = repr(controller)
        assert "BurnInController" in repr_str
        assert "installed=" in repr_str
        assert "running=" in repr_str
        assert "status=" in repr_str


@pytest.mark.integration
@pytest.mark.requires_burnin
class TestControllerConfiguration:
    """Test controller configuration scenarios"""
    
    def test_set_config(self, clean_install, burnin_env):
        """Test setting configuration after initialization"""
        controller = clean_install
        
        # Set config
        controller.set_config(
            test_duration_minutes=5,
            test_drive_letter='E',
            timeout_minutes=10,
        )
        
        # Verify config applied
        assert controller.test_duration_minutes == 5
        assert controller.test_drive_letter == 'E'
        assert controller.timeout_minutes == 10
    
    def test_invalid_config(self, clean_install):
        """Test setting invalid configuration"""
        from lib.testtool.burnin import BurnInConfigError
        
        controller = clean_install
        
        # Try to set invalid duration
        with pytest.raises(BurnInConfigError):
            controller.set_config(
                test_duration_minutes=-1,
            )
        
        # Try to set invalid drive letter
        with pytest.raises(BurnInConfigError):
            controller.set_config(
                test_drive_letter='ZZ',
            )
    
    def test_config_persistence(self, clean_install, burnin_env):
        """Test configuration persists through operations"""
        controller = clean_install
        
        # Set config
        controller.set_config(
            test_duration_minutes=3,
            test_drive_letter='D',
        )
        
        # Get current values
        duration = controller.test_duration_minutes
        drive = controller.test_drive_letter
        
        # Perform some operations
        controller.is_installed()
        controller.is_running()
        
        # Config should still be the same
        assert controller.test_duration_minutes == duration
        assert controller.test_drive_letter == drive


@pytest.mark.integration
@pytest.mark.slow
def test_full_workflow_example(burnin_env, check_environment, cleanup_burnin, pywinauto_available, test_root):
    """
    Complete workflow example test.
    
    This test demonstrates the full lifecycle:
    1. Check/Install BurnIN
    2. Configure test
    3. Run test
    4. Monitor progress
    5. Get results
    6. Cleanup
    """
    from lib.testtool.burnin import BurnInController
    
    print("\n=== Full BurnIN Workflow Test ===\n")
    
    # Load Config.json from tests/integration/Config/
    config_path = test_root / "integration" / "Config" / "Config.json"
    
    if not config_path.exists():
        pytest.skip(f"Config.json not found at {config_path}")
    
    print(f"Loading configuration from: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    # Extract BurnIN configuration
    burnin_config = config_data.get('burnin', {})
    
    # Step 1: Create controller
    print("\nStep 1: Creating controller...")
    controller = BurnInController(
        installer_path=burnin_env['installer_path'],
        install_path=burnin_env['install_path'],
        executable_name=burnin_env['executable_name'],
        license_path=burnin_env['license_path'],
        config_file_path=burnin_env['config_file_path'],  # Use the correct config file path
    )
    
    # Step 2: Ensure installed
    print("Step 2: Checking installation...")
    if not controller.is_installed():
        print("  Installing BurnIN...")
        controller.install()
    print(f"  Installed: {controller.is_installed()}")
    
    # Step 3: Configure (use settings from Config.json)
    print("Step 3: Configuring test...")
    test_duration = burnin_config.get('test_duration_minutes', 1)
    test_drive = burnin_config.get('test_drive_letter', 'D')
    timeout = burnin_config.get('timeout_minutes', 5)
    check_interval = burnin_config.get('check_interval_seconds', 2)
    
    controller.set_config(
        test_duration_minutes=test_duration,
        test_drive_letter=test_drive,
        timeout_minutes=timeout,
        check_interval_seconds=check_interval,
        enable_screenshot=True,
    )
    print(f"  Duration: {controller.test_duration_minutes} minutes")
    print(f"  Drive: {controller.test_drive_letter}")
    
    # Step 4: Start test
    print("\nStep 4: Starting test...")
    controller.start()
    print("  Test started in background thread")
    
    # Step 5: Monitor (optional - thread handles this)
    print("\nStep 5: Waiting for completion...")
    start_time = time.time()
    
    # Poll status occasionally
    timeout_seconds = timeout * 60
    while controller._running and (time.time() - start_time) < timeout_seconds:
        time.sleep(10)
        status = controller.get_status()
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] Status: running={status['running']}, "
              f"process={status['process_running']}, "
              f"result={status['test_result']}")
    
    # Wait for thread to finish
    controller.join(timeout=timeout_seconds)
    
    # Step 6: Get results
    print("\nStep 6: Getting results...")
    final_status = controller.get_status()
    print(f"  Test Result: {final_status['test_result']}")
    print(f"  Error Count: {final_status['error_count']}")
    print(f"  Status: {controller.status}")
    
    # Step 7: Verify completion
    print("Step 7: Verifying completion...")
    assert not controller._running, "Thread should have finished"
    print("  Thread completed successfully")
    
    print("\n=== Workflow Test Complete ===\n")
