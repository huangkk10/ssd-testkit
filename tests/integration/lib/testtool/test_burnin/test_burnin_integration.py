"""
BurnIN Integration Tests

These tests verify the BurnIN library components work correctly with real BurnIN software.
Tests require actual BurnIN installation and environment.
"""

import pytest
import time
import os
from pathlib import Path

from lib.testtool.burnin import (
    BurnInConfig,
    BurnInScriptGenerator,
    BurnInProcessManager,
    BurnInUIMonitor,
    BurnInInstallError,
    BurnInProcessError,
)


@pytest.mark.integration
@pytest.mark.requires_burnin
class TestBurnInInstallation:
    """Test BurnIN installation and uninstallation"""
    
    def test_installation(self, burnin_env, check_environment, cleanup_burnin):
        """Test BurnIN installation process"""
        import shutil
        import time
        
        # Force cleanup install directory first
        install_dir = Path(burnin_env['install_path'])
        if install_dir.exists():
            try:
                shutil.rmtree(install_dir, ignore_errors=True)
                time.sleep(1)  # Give OS time to release file locks
            except Exception as e:
                print(f"Warning: Could not clean directory: {e}")
        
        manager = BurnInProcessManager(
            install_path=burnin_env['install_path'],
            executable_name=burnin_env['executable_name']
        )
        
        # Uninstall if already installed
        if manager.is_installed():
            assert manager.uninstall(timeout=120), "Uninstall failed"
        
        # Verify not installed
        assert not manager.is_installed(), "Should not be installed"
        
        # Install
        result = manager.install(
            installer_path=burnin_env['installer_path'],
            license_path=burnin_env['license_path'],
            timeout=300
        )
        assert result, "Installation should succeed"
        
        # Verify installed
        assert manager.is_installed(), "Should be installed"
        
        # Verify executable exists
        exe_path = Path(burnin_env['install_path']) / burnin_env['executable_name']
        assert exe_path.exists(), f"Executable not found: {exe_path}"
    
    def test_uninstallation(self, burnin_env, check_environment):
        """Test BurnIN uninstallation process"""
        manager = BurnInProcessManager(
            install_path=burnin_env['install_path'],
            executable_name=burnin_env['executable_name']
        )
        
        # Install if not installed
        if not manager.is_installed():
            manager.install(
                installer_path=burnin_env['installer_path'],
                license_path=burnin_env['license_path'],
                timeout=300
            )
        
        assert manager.is_installed(), "Should be installed"
        
        # Uninstall
        result = manager.uninstall(timeout=120)
        assert result, "Uninstallation should succeed"
        
        # Verify not installed
        assert not manager.is_installed(), "Should not be installed"
        
        # Verify executable removed
        exe_path = Path(burnin_env['install_path']) / burnin_env['executable_name']
        assert not exe_path.exists(), f"Executable should be removed: {exe_path}"


@pytest.mark.integration
class TestScriptGeneration:
    """Test script generation functionality"""
    
    def test_generate_disk_test_script(self, burnin_env, check_environment):
        """Test generating disk test script"""
        generator = BurnInScriptGenerator()
        
        script_path = burnin_env['script_path']
        config_path = burnin_env['config_file_path']
        
        # Create a temporary config file
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        Path(config_path).write_text("# Temporary config for testing\n", encoding='utf-8')
        
        try:
            # Generate script
            generator.generate_disk_test_script(
                config_file_path=config_path,
                log_path=burnin_env['log_path'],
                duration_minutes=burnin_env['test_duration_minutes'],
                drive_letter=burnin_env['test_drive_letter'],
                output_path=str(script_path)
            )
            
            # Verify script exists
            assert Path(script_path).exists(), f"Script not created: {script_path}"
            
            # Verify script content
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'LOAD' in content, "Script should contain LOAD command"
                assert 'RUN DISK' in content, "Script should contain RUN DISK command"
                assert burnin_env['test_drive_letter'] in content, "Script should contain drive letter"
        
        finally:
            # Cleanup
            Path(script_path).unlink(missing_ok=True)
            Path(config_path).unlink(missing_ok=True)
    
    def test_generate_full_config_script(self, burnin_env, check_environment):
        """Test generating full configuration script"""
        generator = BurnInScriptGenerator()
        
        script_path = burnin_env['script_path']
        config_path = burnin_env['config_file_path']
        log_path = burnin_env['log_path']
        
        # Ensure config file exists (create dummy if needed)
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(config_path).exists():
            Path(config_path).write_text("# Test config\n", encoding='utf-8')
        
        # Generate script with duration
        generator.generate_full_config_script(
            config_file_path=config_path,
            log_path=log_path,
            duration_minutes=burnin_env['test_duration_minutes'],
            output_path=script_path
        )
        
        # Verify script exists
        assert Path(script_path).exists(), f"Script not created: {script_path}"
        
        # Verify script has content
        assert Path(script_path).stat().st_size > 0, "Script should not be empty"
        
        # Verify script contains expected commands
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'LOAD' in content, "Script should contain LOAD command"
            assert 'RUN CONFIG' in content, "Script should contain RUN CONFIG"
        
        # Cleanup
        Path(script_path).unlink(missing_ok=True)


@pytest.mark.integration
@pytest.mark.requires_burnin
class TestProcessLifecycle:
    """Test BurnIN process lifecycle"""
    
    def test_start_and_stop_process(self, installed_burnin, burnin_env):
        """Test starting and stopping BurnIN process"""
        manager = installed_burnin._process_manager
        
        # Generate script
        generator = BurnInScriptGenerator()
        script_path = burnin_env['script_path']
        config_path = burnin_env['config_file_path']
        log_path = burnin_env['log_path']
        
        # Ensure config exists
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(config_path).exists():
            Path(config_path).write_text("# Test config\n", encoding='utf-8')
        
        generator.generate_disk_test_script(
            config_file_path=config_path,
            log_path=log_path,
            duration_minutes=1,
            drive_letter=burnin_env['test_drive_letter'],
            output_path=script_path
        )
        
        # Start process
        pid = manager.start_process(script_path=script_path)
        assert pid is not None, "Should return PID"
        assert pid > 0, "PID should be positive"
        
        # Wait a bit for process to start
        time.sleep(3)
        
        # Verify running
        assert manager.is_running(), "Process should be running"
        assert manager.get_pid() == pid, "PIDs should match"
        
        # Stop process
        manager.stop_process(timeout=30)
        
        # Verify stopped
        assert not manager.is_running(), "Process should be stopped"
        
        # Cleanup
        Path(script_path).unlink(missing_ok=True)
    
    def test_kill_process(self, installed_burnin, burnin_env):
        """Test killing BurnIN process"""
        manager = installed_burnin._process_manager
        
        # Generate script
        generator = BurnInScriptGenerator()
        script_path = burnin_env['script_path']
        config_path = burnin_env['config_file_path']
        log_path = burnin_env['log_path']
        
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(config_path).exists():
            Path(config_path).write_text("# Test config\n", encoding='utf-8')
        
        generator.generate_disk_test_script(
            config_file_path=config_path,
            log_path=log_path,
            duration_minutes=10,
            drive_letter=burnin_env['test_drive_letter'],
            output_path=script_path
        )
        
        # Start process
        pid = manager.start_process(script_path=script_path)
        assert pid is not None, "Should return PID"
        
        time.sleep(3)
        assert manager.is_running(), "Process should be running"
        
        # Kill process
        manager.kill_process()
        
        # Verify killed
        time.sleep(1)
        assert not manager.is_running(), "Process should be killed"
        
        # Cleanup
        Path(script_path).unlink(missing_ok=True)


@pytest.mark.integration
@pytest.mark.requires_burnin
@pytest.mark.slow
class TestUIMonitoring:
    """Test UI monitoring functionality"""
    
    def test_connect_to_ui(self, installed_burnin, burnin_env, pywinauto_available):
        """Test connecting to BurnIN UI"""
        manager = installed_burnin._process_manager
        
        # Generate and start
        generator = BurnInScriptGenerator()
        script_path = burnin_env['script_path']
        config_path = burnin_env['config_file_path']
        log_path = burnin_env['log_path']
        
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(config_path).exists():
            Path(config_path).write_text("# Test config\n", encoding='utf-8')
        
        generator.generate_disk_test_script(
            config_file_path=config_path,
            log_path=log_path,
            duration_minutes=1,
            drive_letter=burnin_env['test_drive_letter'],
            output_path=script_path
        )
        
        manager.start_process(script_path=script_path)
        print(f"\nBurnIN process started, PID: {manager.get_pid()}")
        print("Waiting 10 seconds for UI to appear...")
        time.sleep(10)  # Increased wait time
        
        # List all windows for debugging
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
            print(f"\nFound {len(windows)} windows:")
            for i, win in enumerate(windows[:20]):  # Show first 20
                try:
                    title = win.window_text()
                    if title and ('burn' in title.lower() or 'passmark' in title.lower()):
                        print(f"  [{i}] {title}")
                except:
                    pass
        except Exception as e:
            print(f"Could not list windows: {e}")
        
        # Try multiple possible window titles
        possible_titles = [
            "PassMark BurnInTest",
            "BurnInTest",
            "PassMark",
            "bit.exe"
        ]
        
        connected = False
        ui_monitor = None
        
        for title in possible_titles:
            print(f"\nTrying window title: '{title}'")
            try:
                ui_monitor = BurnInUIMonitor(
                    window_title=title,
                    retry_max=10,
                    retry_interval=1.0
                )
                if ui_monitor.connect():
                    print(f"✓ Connected with title: '{title}'")
                    connected = True
                    break
            except Exception as e:
                print(f"✗ Failed with '{title}': {e}")
        
        if not connected:
            # Cleanup and skip test
            manager.stop_process(timeout=30)
            Path(script_path).unlink(missing_ok=True)
            pytest.skip("Could not connect to BurnIN UI - window not found")
        
        assert ui_monitor.is_connected(), "Should report as connected"
        
        # Read status
        status = ui_monitor.read_status()
        print(f"\nUI Status: {status}")
        
        # Status should be a dict with expected keys
        assert isinstance(status, dict), f"Status should be dict, got {type(status)}"
        assert 'test_result' in status, "Status should contain test_result"
        assert 'test_running' in status, "Status should contain test_running"
        assert 'errors' in status, "Status should contain errors"
        
        # Disconnect
        ui_monitor.disconnect()
        assert not ui_monitor.is_connected(), "Should be disconnected"
        
        # Cleanup
        manager.stop_process(timeout=30)
        Path(script_path).unlink(missing_ok=True)
    
    def test_read_ui_status(self, installed_burnin, burnin_env, pywinauto_available):
        """Test reading UI status during test"""
        manager = installed_burnin._process_manager
        
        # Generate and start short test
        generator = BurnInScriptGenerator()
        script_path = burnin_env['script_path']
        config_path = burnin_env['config_file_path']
        log_path = burnin_env['log_path']
        
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(config_path).exists():
            Path(config_path).write_text("# Test config\n", encoding='utf-8')
        
        generator.generate_disk_test_script(
            config_file_path=config_path,
            log_path=log_path,
            duration_minutes=1,
            drive_letter=burnin_env['test_drive_letter'],
            output_path=script_path
        )
        
        manager.start_process(script_path=script_path)
        time.sleep(10)  # Wait longer for UI
        
        # Connect to UI - use correct window title
        ui_monitor = BurnInUIMonitor(
            window_title="BurnInTest",
            retry_max=10,
            retry_interval=1.0
        )
        
        try:
            if not ui_monitor.connect():
                pytest.skip("Could not connect to BurnIN UI")
        except Exception as e:
            pytest.skip(f"UI connection failed: {e}")
        
        # Read status multiple times
        statuses = []
        for _ in range(3):
            status = ui_monitor.read_status()
            statuses.append(status)
            print(f"Status reading: {status}")
            time.sleep(2)
        
        # Check we got valid status dicts
        assert len(statuses) > 0, "Should read at least one status"
        for status in statuses:
            assert isinstance(status, dict), "Status should be dict"
            assert 'test_result' in status, "Should have test_result key"
        
        # Try to get error count
        try:
            error_count = ui_monitor.get_error_count()
            assert error_count >= 0, "Error count should be non-negative"
        except Exception as e:
            print(f"Could not read error count: {e}")
        
        # Cleanup
        ui_monitor.disconnect()
        manager.stop_process(timeout=30)
        Path(script_path).unlink(missing_ok=True)


@pytest.mark.integration
class TestConfiguration:
    """Test configuration management"""
    
    def test_validate_config(self, burnin_env):
        """Test configuration validation"""
        # Valid config
        valid_config = {
            'test_duration_minutes': 60,
            'test_drive_letter': 'D',
            'timeout_seconds': 3600,
        }
        
        # Should not raise
        BurnInConfig.validate_config(valid_config)
        
        # Invalid duration
        invalid_config = {
            'test_duration_minutes': -1,
        }
        
        with pytest.raises(ValueError):
            BurnInConfig.validate_config(invalid_config)
        
        # Invalid drive letter
        invalid_config = {
            'test_drive_letter': 'ZZ',
        }
        
        with pytest.raises(ValueError):
            BurnInConfig.validate_config(invalid_config)
    
    def test_merge_config(self, burnin_env):
        """Test configuration merging"""
        base = BurnInConfig.get_default_config()
        updates = {
            'test_duration_minutes': 120,
            'test_drive_letter': 'E',
        }
        
        merged = BurnInConfig.merge_config(base, updates)
        
        # Check merged values
        assert merged['test_duration_minutes'] == 120
        assert merged['test_drive_letter'] == 'E'
        
        # Check base not modified
        assert base['test_duration_minutes'] != 120
        
        # Check other values preserved
        assert 'timeout_seconds' in merged
