"""
Direct SmartCheck.bat Test - Bypass Python Wrapper
Directly test SmartCheck.bat - no Python wrapper

This test directly executes SmartCheck.bat to understand its REAL behavior:
- Where does it create output directories?
- What files does it generate?
- What is the actual status file format?
- How does it actually work without Python wrapper?

Key Discovery:
- SmartCheck.bat creates: bin/SmiWinTools/log_SmartCheck/YYYYMMDDHHMMSS/
- Status file is: SmartCheck.ini (NOT RunCard.ini!)
- Format includes: version, test_cases, cycle, loop, start_time, elapsed_time, test_result, err_msg
"""

import pytest
import subprocess
import os
import time
from pathlib import Path
from datetime import datetime
import configparser
import glob
import shutil


class TestDirectSmartCheckBat:
    """Directly test the real behavior of SmartCheck.bat."""
    
    @pytest.fixture
    def smiwintools_dir(self):
        """Directory that contains SmartCheck.bat."""
        return Path(__file__).resolve().parent.parent / "bin" / "SmiWinTools"
    
    @pytest.fixture
    def smartcheck_bat(self, smiwintools_dir):
        """Full path to SmartCheck.bat."""
        return smiwintools_dir / "SmartCheck.bat"
    
    @pytest.fixture(autouse=True)
    def cleanup_logs(self, smiwintools_dir):
        """Clean log_SmartCheck directory before/after tests."""
        log_dir = smiwintools_dir / "log_SmartCheck"
        
        # Do not delete before test; let SmartCheck.bat create a new timestamp directory
        # if log_dir.exists():
        #     print(f"\n  [Cleanup] log_SmartCheck directory exists, keeping...")
        # else:
        #     print(f"\n  [Cleanup] log_SmartCheck directory does not exist")
        
        yield
        
        # Keep logs after test for inspection
        if log_dir.exists():
            print(f"\n  [Kept logs] {log_dir}")
    
    def find_latest_smartcheck_log_dir(self, smiwintools_dir):
        """Find the newest SmartCheck log directory."""
        log_base = smiwintools_dir / "log_SmartCheck"
        if not log_base.exists():
            return None
        
        # Find all timestamp directories (format: YYYYMMDDHHMMSS)
        timestamp_dirs = [d for d in log_base.iterdir() if d.is_dir() and d.name.isdigit()]
        if not timestamp_dirs:
            return None
        
        # Return the latest (sorted by name; largest is newest)
        return max(timestamp_dirs, key=lambda d: d.name)
    
    def read_smartcheck_ini(self, smartcheck_ini_path):
        """Read SmartCheck.ini (large config file with full settings)."""
        if not smartcheck_ini_path.exists():
            return None
        
        config = configparser.ConfigParser()
        config.read(smartcheck_ini_path)
        
        # SmartCheck.ini is a config file with a [global] section
        if 'global' in config:
            return {
                'case': config['global'].get('case', ''),
                'output_dir': config['global'].get('output_dir', ''),
                'total_cycle': config['global'].get('total_cycle', ''),
                'total_time': config['global'].get('total_time', ''),
                'dut_id': config['global'].get('dut_id', ''),
                'enable_monitor_smart': config['global'].get('enable_monitor_smart', ''),
            }
        return None
    
    def read_runcard_ini(self, runcard_ini_path):
        """Read RunCard.ini status file (small file, status only)."""
        if not runcard_ini_path.exists():
            return None
        
        config = configparser.ConfigParser()
        config.read(runcard_ini_path)
        
        # Try different section names
        for section_name in ['Test Status', 'Result', 'STATUS']:
            if section_name in config:
                status = {}
                for key, value in config[section_name].items():
                    status[key] = value
                return status
        
        return None
    
    def test_direct_smartcheck_bat_execution(self, smartcheck_bat, smiwintools_dir):
        """
        Test 1: Execute SmartCheck.bat directly and observe real behavior
        
        Observation focus:
        1. Whether SmartCheck.bat starts successfully
        2. When log_SmartCheck is created
        3. Timestamp subdirectory naming format
        4. SmartCheck.ini contents and changes
        5. Other generated files
        """
        print("\n" + "="*80)
        print("Direct test SmartCheck.bat - observe real behavior")
        print("="*80)
        
        # 1. Check whether SmartCheck.bat exists
        print(f"\n[1] Check SmartCheck.bat:")
        print(f"  Path: {smartcheck_bat}")
        print(f"  Exists: {smartcheck_bat.exists()}")
        
        if not smartcheck_bat.exists():
            pytest.skip(f"SmartCheck.bat not found at {smartcheck_bat}")
        
        # 2. Check working directory
        print(f"\n[2] Working directory:")
        print(f"  SmiWinTools: {smiwintools_dir}")
        print(f"  Current directory: {os.getcwd()}")
        
        # 3. Start SmartCheck.bat
        print(f"\n[3] Start SmartCheck.bat:")
        print(f"  Start time: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
        
        # Check for existing log directories
        log_base_dir = smiwintools_dir / "log_SmartCheck"
        if log_base_dir.exists():
            existing_dirs = list(log_base_dir.iterdir())
            print(f"  ⚠️ log_SmartCheck exists and contains {len(existing_dirs)} subdirectories")
            if existing_dirs:
                print(f"  Latest directory: {max(existing_dirs, key=lambda d: d.name).name}")
        
        # Switch to SmiWinTools directory for execution (important!)
        original_dir = os.getcwd()
        os.chdir(smiwintools_dir)
        
        # Check for SmiCli2.exe
        smicli_path = smiwintools_dir / "bin" / "x64" / "SmiCli2.exe"
        print(f"  SmiCli2.exe exists: {smicli_path.exists()}")
        
        try:
            # Start process
            process = subprocess.Popen(
                str(smartcheck_bat),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(smiwintools_dir)
            )
            print(f"  Process PID: {process.pid}")
            print(f"  Process started successfully")
            
            # 4. Monitor creation of log_SmartCheck directory
            print(f"\n[4] Monitor creation of log_SmartCheck and process status:")
            
            monitor_duration = 120  # monitor for 120 seconds
            check_interval = 2  # check every 2 seconds
            log_dir_found = False
            latest_log_dir = None
            initial_log_dirs = set()
            
            # Record initial state
            if log_base_dir.exists():
                initial_log_dirs = {d.name for d in log_base_dir.iterdir() if d.is_dir()}
            
            for i in range(int(monitor_duration / check_interval)):
                time.sleep(check_interval)
                current_time = datetime.now().strftime('%H:%M:%S')
                
                # Check process status
                returncode = process.poll()
                if returncode is not None:
                    print(f"  [{i+1}] {current_time} - ⚠️ SmartCheck.bat ended (returncode={returncode})")
                    
                    # Check whether a new directory was created
                    if log_base_dir.exists():
                        current_log_dirs = {d.name for d in log_base_dir.iterdir() if d.is_dir()}
                        new_dirs = current_log_dirs - initial_log_dirs
                        if new_dirs:
                            print(f"       Found new directories: {', '.join(new_dirs)}")
                            latest_log_dir = log_base_dir / max(new_dirs)
                        else:
                            print(f"       ⚠️ No new directories created")
                    break
                
                # Check log_SmartCheck directory
                if log_base_dir.exists():
                    current_log_dirs = {d.name for d in log_base_dir.iterdir() if d.is_dir()}
                    new_dirs = current_log_dirs - initial_log_dirs
                    
                    if new_dirs and not log_dir_found:
                        print(f"  [{i+1}] {current_time} - 🎯 log_SmartCheck created new directory")
                        log_dir_found = True
                        initial_log_dirs = current_log_dirs
                
                # Find timestamp subdirectory
                if log_dir_found:
                    latest_log_dir = self.find_latest_smartcheck_log_dir(smiwintools_dir)
                    if latest_log_dir:
                        print(f"  [{i+1}] {current_time} - 📁 Found log directory: {latest_log_dir.name}")
                        
                        # Read RunCard.ini (status file)
                        runcard_ini = latest_log_dir / "RunCard.ini"
                        if runcard_ini.exists():
                            status = self.read_runcard_ini(runcard_ini)
                            if status:
                                print(f"       ✅ RunCard.ini contents:")
                                for key, value in status.items():
                                    print(f"          {key}: {value}")
                                
                                # If not ONGOING, test is complete
                                test_result = status.get('test_result', '').upper()
                                if test_result not in ['ONGOING', '']:
                                    print(f"  [{i+1}] {current_time} - ✅ Test complete ({test_result})")
                                    break
                        break
                else:
                    print(f"  [{i+1}] {current_time} - Waiting for log_SmartCheck directory...")
            
            # 5. Final status check
            print(f"\n[5] Final status check:")
            
            # Try to find latest directory (even if process ended early)
            if not latest_log_dir:
                latest_log_dir = self.find_latest_smartcheck_log_dir(smiwintools_dir)
            
            if latest_log_dir:
                print(f"  Log directory: {latest_log_dir}")
                print(f"  Directory name: {latest_log_dir.name}")
                print(f"  Creation time: {datetime.strptime(latest_log_dir.name, '%Y%m%d%H%M%S').strftime('%Y/%m/%d %H:%M:%S')}")
                print(f"  Log directory: {latest_log_dir}")
                
                # List all files
                print(f"\n  Generated files:")
                for file in sorted(latest_log_dir.iterdir()):
                    if file.is_file():
                        size = file.stat().st_size
                        print(f"    - {file.name} ({size} bytes)")
                    else:
                        print(f"    - {file.name}/ (directory)")
                
                # Read RunCard.ini (status file - small file)
                runcard_ini = latest_log_dir / "RunCard.ini"
                if runcard_ini.exists():
                    print(f"\n  ✅ RunCard.ini (status file):")
                    status = self.read_runcard_ini(runcard_ini)
                    if status:
                        for key, value in status.items():
                            print(f"    {key}: {value}")
                    
                    print(f"\n  RunCard.ini raw contents:")
                    with open(runcard_ini, 'r', encoding='utf-8') as f:
                        for line in f:
                            print(f"    {line.rstrip()}")
                else:
                    print(f"\n  ⚠️ RunCard.ini not found")
                
                # Read SmartCheck.ini (config file - large file)
                smartcheck_ini = latest_log_dir / "SmartCheck.ini"
                if smartcheck_ini.exists():
                    print(f"\n  📝 SmartCheck.ini (config file) key info:")
                    config_info = self.read_smartcheck_ini(smartcheck_ini)
                    if config_info:
                        for key, value in config_info.items():
                            print(f"    {key}: {value}")
                else:
                    print(f"\n  ⚠️ SmartCheck.ini not found")
            else:
                print(f"  ⚠️ No log directory found")
            
            # 6. Wait for process to exit or timeout
                print(f"\n[6] Waiting for process to finish:")
            try:
                process.wait(timeout=10)
                print(f"  Process exited normally (returncode={process.returncode})")
            except subprocess.TimeoutExpired:
                print(f"  Process still running, terminating...")
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
                print(f"  Process terminated")
            
        finally:
            # Restore original working directory
            os.chdir(original_dir)
        
        print("\n" + "="*80)
        print("Test complete")
        print("="*80)
    
    def test_smartcheck_bat_output_structure(self, smartcheck_bat, smiwintools_dir):
        """
        Test 2: Verify SmartCheck.bat output directory structure
        
        Expected structure:
        bin/SmiWinTools/
        ├── SmartCheck.bat
        └── log_SmartCheck/
            └── YYYYMMDDHHMMSS/  (e.g., 20260210103523)
                ├── SmartCheck.ini
                └── ... (other log files)
        """
        print("\n" + "="*80)
        print("Verify SmartCheck.bat output directory structure")
        print("="*80)
        
        if not smartcheck_bat.exists():
            pytest.skip(f"SmartCheck.bat not found")
        
        # Execute SmartCheck.bat (short run)
        original_dir = os.getcwd()
        os.chdir(smiwintools_dir)
        
        try:
            process = subprocess.Popen(
                str(smartcheck_bat),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(smiwintools_dir)
            )
            
            # Wait enough time for directory creation
            time.sleep(10)
            
            # Verify directory structure
            log_base = smiwintools_dir / "log_SmartCheck"
            assert log_base.exists(), "log_SmartCheck directory should be created"
            
            latest_log_dir = self.find_latest_smartcheck_log_dir(smiwintools_dir)
            assert latest_log_dir is not None, "There should be a timestamp subdirectory"
            
            # Verify timestamp format (14 digits: YYYYMMDDHHMMSS)
            assert len(latest_log_dir.name) == 14, f"Timestamp format should be 14 digits: {latest_log_dir.name}"
            assert latest_log_dir.name.isdigit(), f"Timestamp should be numeric: {latest_log_dir.name}"
            
            # Verify SmartCheck.ini exists
            smartcheck_ini = latest_log_dir / "SmartCheck.ini"
            assert smartcheck_ini.exists(), "SmartCheck.ini should exist"
            
            print(f"✅ Directory structure verification passed")
            print(f"  log_SmartCheck: {log_base}")
            print(f"  Timestamp directory: {latest_log_dir.name}")
            print(f"  SmartCheck.ini: exists")
            
            # Cleanup
            process.terminate()
            process.wait(timeout=5)
            
        finally:
            os.chdir(original_dir)
        
        print("="*80)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
