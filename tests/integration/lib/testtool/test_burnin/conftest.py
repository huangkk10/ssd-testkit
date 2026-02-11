"""
Integration Test Fixtures and Configuration

This module provides pytest fixtures and configuration for BurnIN integration tests.
"""

import os
import time
import shutil
import pytest
from pathlib import Path
from typing import Dict, Any


def pytest_configure(config):
    """Configure pytest for integration tests"""
    # Register custom markers
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real environment)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_burnin: mark test as requiring BurnIN installation"
    )


@pytest.fixture(scope="session")
def test_root():
    """Get test root directory"""
    return Path(__file__).parent.parent.parent.parent.parent


@pytest.fixture(scope="session")
def burnin_env(test_root) -> Dict[str, Any]:
    """
    Provide BurnIN test environment configuration.
    
    This fixture provides paths and settings for integration tests.
    Values can be overridden with environment variables.
    
    Returns:
        Dictionary with test environment configuration
    """
    # Default paths - use existing BurnIN files from unit test directory
    burnin_bin_path = test_root / "unit" / "lib" / "testtool" / "bin" / "BurnIn"
    default_installer = burnin_bin_path / "bitwindows.exe"
    default_license = burnin_bin_path / "key.dat"
    
    # Path to config file - use centralized integration test config
    config_file_path = test_root / "integration" / "Config" / "BIT_Config" / "BurnInScript.bitcfg"
    
    # Allow environment variable overrides
    installer_path = os.getenv("BURNIN_INSTALLER_PATH", str(default_installer))
    license_path = os.getenv("BURNIN_LICENSE_PATH", str(default_license))
    test_drive = os.getenv("BURNIN_TEST_DRIVE", "D")
    
    # Use unique path for each test session to avoid conflicts
    import time
    timestamp = int(time.time())
    install_path = os.getenv("BURNIN_INSTALL_PATH", 
                             str(test_root / "testlog" / f"BurnInTest_{timestamp}"))
    
    # Setup testlog directory
    testlog_dir = test_root / "testlog"
    testlog_dir.mkdir(parents=True, exist_ok=True)
    
    env_config = {
        # Paths
        'installer_path': installer_path,
        'license_path': license_path if Path(license_path).exists() else None,
        'install_path': install_path,
        'executable_name': "bit.exe",
        
        # Test parameters
        'test_drive_letter': test_drive,
        'test_duration_minutes': 1,  # Short duration for testing
        'timeout_seconds': 300,  # 5 minutes timeout
        'check_interval_seconds': 2,
        
        # Paths for generated files
        'script_path': str(testlog_dir / "test_script.bits"),
        'log_path': str(testlog_dir / "integration_test.log"),
        'config_file_path': str(config_file_path),
        
        # Environment info
        'test_root': str(test_root),
    }
    
    return env_config


@pytest.fixture(scope="session")
def check_environment(burnin_env):
    """
    Check if environment is ready for integration tests.
    
    Validates that required files and settings are available.
    Skips tests if environment is not ready.
    """
    issues = []
    
    # Check installer exists
    if not Path(burnin_env['installer_path']).exists():
        issues.append(f"Installer not found: {burnin_env['installer_path']}")
    
    # Check if running on Windows
    if os.name != 'nt':
        issues.append("BurnIN tests require Windows OS")
    
    # Check if testlog directory is writable
    testlog_dir = Path(burnin_env['test_root']) / "testlog"
    testlog_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(testlog_dir, os.W_OK):
        issues.append(f"Cannot write to testlog directory: {testlog_dir}")
    
    if issues:
        pytest.skip(
            "Environment not ready for integration tests:\n" + 
            "\n".join(f"  - {issue}" for issue in issues)
        )
    
    return True


@pytest.fixture
def cleanup_burnin(burnin_env):
    """
    Fixture to ensure BurnIN is cleaned up after test.
    
    This fixture runs after each test to uninstall BurnIN if it's still installed.
    Helps ensure test isolation.
    """
    from lib.testtool.burnin import BurnInProcessManager
    
    yield  # Run the test
    
    # Cleanup after test
    try:
        manager = BurnInProcessManager(
            install_path=burnin_env['install_path'],
            executable_name="bit.exe"
        )
        
        # Stop any running processes
        if manager.is_running():
            try:
                manager.stop_process(timeout=10)
            except Exception:
                try:
                    manager.kill_process()
                except Exception:
                    pass
        
        # Uninstall if installed
        if manager.is_installed():
            try:
                manager.uninstall(timeout=60)
            except Exception as e:
                print(f"Warning: Cleanup uninstall failed: {e}")
    
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")


@pytest.fixture
def burnin_controller(burnin_env, check_environment):
    """
    Provide a configured BurnInController instance for testing.
    
    Creates a controller with test configuration.
    Automatically checks environment before test.
    """
    from lib.testtool.burnin import BurnInController
    
    controller = BurnInController(
        installer_path=burnin_env['installer_path'],
        install_path=burnin_env['install_path'],
        executable_name=burnin_env['executable_name'],
        license_path=burnin_env['license_path'],
        test_duration_minutes=burnin_env['test_duration_minutes'],
        test_drive_letter=burnin_env['test_drive_letter'],
        timeout_seconds=burnin_env['timeout_seconds'],
        check_interval_seconds=burnin_env['check_interval_seconds'],
        script_path=burnin_env['script_path'],
        log_path=burnin_env['log_path'],
        config_file_path=burnin_env['config_file_path'],
    )
    
    return controller


@pytest.fixture
def installed_burnin(burnin_controller, cleanup_burnin):
    """
    Ensure BurnIN is installed (but don't force reinstall).
    
    Use this for tests that just need BurnIN to be available,
    not necessarily freshly installed.
    """
    # Only install if not already installed
    if not burnin_controller.is_installed():
        try:
            burnin_controller.install()
        except Exception as e:
            import pytest
            pytest.skip(f"Cannot install BurnIN: {e}")
    
    yield burnin_controller


@pytest.fixture
def clean_install(burnin_controller, cleanup_burnin):
    """
    Ensure BurnIN is freshly installed for test.
    
    Uninstalls if already installed, then installs fresh.
    Cleans up after test.
    """
    import shutil
    
    # Force cleanup install directory first
    install_dir = Path(burnin_controller.install_path)
    if install_dir.exists():
        try:
            # Stop any running processes first
            if burnin_controller._process_manager and burnin_controller.is_running():
                try:
                    burnin_controller.stop(timeout=10)
                except Exception:
                    pass
            
            # Kill any BurnIN processes
            try:
                import subprocess
                subprocess.run(['taskkill', '/F', '/IM', 'bit.exe'], 
                             capture_output=True, timeout=10)
                subprocess.run(['taskkill', '/F', '/IM', 'bitwindows.exe'], 
                             capture_output=True, timeout=10)
                time.sleep(2)
            except Exception:
                pass
            
            # Try to remove directory with multiple attempts
            for attempt in range(3):
                try:
                    if install_dir.exists():
                        # First try normal removal
                        shutil.rmtree(install_dir, ignore_errors=True)
                        time.sleep(1)
                        
                        # If still exists, try forced removal
                        if install_dir.exists():
                            subprocess.run(['cmd', '/c', 'rmdir', '/S', '/Q', str(install_dir)],
                                         capture_output=True, timeout=30)
                            time.sleep(1)
                        
                        if not install_dir.exists():
                            break
                except Exception:
                    pass
                
                time.sleep(2)  # Wait before retry
        except Exception as e:
            print(f"Warning: Could not clean install directory: {e}")
    
    # Uninstall if currently installed
    if burnin_controller.is_installed():
        try:
            burnin_controller.uninstall()
        except Exception as e:
            print(f"Warning: Uninstall failed: {e}")
    
    # Try to install fresh
    try:
        burnin_controller.install()
    except Exception as e:
        # If installation fails with permission error, skip tests requiring fresh install
        import pytest
        pytest.skip(f"Cannot install BurnIN (requires administrator privileges): {e}")
    
    yield burnin_controller
    
    # Cleanup handled by cleanup_burnin fixture


@pytest.fixture(scope="session")
def pywinauto_available():
    """Check if pywinauto is available"""
    try:
        import pywinauto
        return True
    except ImportError:
        pytest.skip("pywinauto not installed (required for UI tests)")
        return False
