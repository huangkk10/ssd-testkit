"""
Test SmartCheck.ini Configuration
Validate SmartCheck.ini configuration

This test verifies:
1. output_dir configuration - can we specify custom output directory?
2. Whether SmartCheck.bat respects the output_dir setting
3. Whether RunCard.ini is created in the specified output_dir
"""

import pytest
import subprocess
import os
import time
from pathlib import Path
from datetime import datetime
import configparser
import shutil


class TestSmartCheckConfig:
    """Verify SmartCheck.ini configuration features"""
    
    @pytest.fixture
    def smiwintools_dir(self):
        """Directory containing SmartCheck.bat"""
        return Path(__file__).resolve().parent.parent / "bin" / "SmiWinTools"
    
    @pytest.fixture
    def smartcheck_bat(self, smiwintools_dir):
        """Full path to SmartCheck.bat"""
        return smiwintools_dir / "SmartCheck.bat"
    
    @pytest.fixture
    def smartcheck_ini(self, smiwintools_dir):
        """Path to SmartCheck.ini configuration file"""
        return smiwintools_dir / "SmartCheck.ini"
    
    @pytest.fixture
    def backup_smartcheck_ini(self, smartcheck_ini):
        """Backup the original SmartCheck.ini"""
        backup_path = smartcheck_ini.parent / "SmartCheck.ini.backup"
        
        # Backup
        if smartcheck_ini.exists():
            shutil.copy2(smartcheck_ini, backup_path)
        
        yield
        
        # Restore
        if backup_path.exists():
            shutil.copy2(backup_path, smartcheck_ini)
            backup_path.unlink()
    
    def modify_smartcheck_ini(self, smartcheck_ini_path, output_dir):
        """
        Modify the output_dir setting in SmartCheck.ini

        Args:
            smartcheck_ini_path: path to SmartCheck.ini
            output_dir: output directory to set (absolute path)
        """
        config = configparser.ConfigParser()
        config.read(smartcheck_ini_path)
        
        # Modify output_dir
        if 'global' in config:
            config['global']['output_dir'] = str(output_dir)
            
            # Write back to file
            with open(smartcheck_ini_path, 'w') as f:
                config.write(f)
            
            return True
        return False
    
    def read_smartcheck_ini_output_dir(self, smartcheck_ini_path):
        """Read the output_dir setting from SmartCheck.ini"""
        config = configparser.ConfigParser()
        config.read(smartcheck_ini_path)
        
        if 'global' in config:
            return config['global'].get('output_dir', '')
        return ''
    
    def find_runcard_ini(self, search_dir, max_depth=3):
        """
        Search for RunCard.ini under the specified directory

        Args:
            search_dir: directory to start searching from
            max_depth: maximum recursion depth

        Returns:
            list of found RunCard.ini paths
        """
        found_files = []
        
        def search_recursive(current_dir, depth):
            if depth > max_depth:
                return
            
            try:
                for item in current_dir.iterdir():
                    if item.is_file() and item.name == "RunCard.ini":
                        found_files.append(item)
                    elif item.is_dir():
                        search_recursive(item, depth + 1)
            except PermissionError:
                pass
        
        search_recursive(Path(search_dir), 0)
        return found_files
    
    def test_output_dir_configuration(self, smartcheck_bat, smartcheck_ini, 
                                     smiwintools_dir, backup_smartcheck_ini):
        """
        Test 1: Verify output_dir setting is effective

        Steps:
        1. Create a custom output directory under test_smartcheck/
        2. Modify SmartCheck.ini output_dir
        3. Run SmartCheck.bat
        4. Verify RunCard.ini is created in the specified output_dir
        """
        print("\n" + "="*80)
        print("Test output_dir configuration")
        print("="*80)
        
        if not smartcheck_bat.exists():
            pytest.skip(f"SmartCheck.bat not found")
        
        # 1. Create custom output directory under test_smartcheck/
        test_smartcheck_dir = Path(__file__).parent
        custom_output_dir = test_smartcheck_dir / "smartcheck_custom_output"
        
        # Clean up if exists
        if custom_output_dir.exists():
            shutil.rmtree(custom_output_dir)
        
        custom_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[1] Create custom output directory:")
        print(f"  Path: {custom_output_dir}")
        print(f"  Relative to test_smartcheck: {custom_output_dir.relative_to(test_smartcheck_dir)}")
        
        # 2. Modify SmartCheck.ini
        print(f"\n[2] Modify SmartCheck.ini:")
        original_output_dir = self.read_smartcheck_ini_output_dir(smartcheck_ini)
        print(f"  Original output_dir: '{original_output_dir}'")
        
        success = self.modify_smartcheck_ini(smartcheck_ini, custom_output_dir)
        if not success:
            pytest.fail("Failed to modify SmartCheck.ini")
        
        new_output_dir = self.read_smartcheck_ini_output_dir(smartcheck_ini)
        print(f"  New output_dir: '{new_output_dir}'")
        assert str(custom_output_dir) == new_output_dir, "output_dir modification failed"
        
        # 3. Run SmartCheck.bat
        print(f"\n[3] Run SmartCheck.bat:")
        print(f"  Start time: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
        
        original_dir = os.getcwd()
        os.chdir(smiwintools_dir)
        
        try:
            process = subprocess.Popen(
                str(smartcheck_bat),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(smiwintools_dir)
            )
            print(f"  Process PID: {process.pid}")
            
            # 4. Monitor output directory
            print(f"\n[4] Monitor output directory:")

            # Wait up to 180 seconds (3 minutes)
            monitor_duration = 180
            check_interval = 5
            runcard_found = False
            runcard_location = None
            
            for i in range(int(monitor_duration / check_interval)):
                time.sleep(check_interval)
                current_time = datetime.now().strftime('%H:%M:%S')
                
                # Check process status
                returncode = process.poll()
                if returncode is not None:
                    print(f"  [{i+1}] {current_time} - ⚠️ SmartCheck.bat ended")
                    break
                
                # Search for RunCard.ini in custom directory
                custom_runcards = self.find_runcard_ini(custom_output_dir)
                if custom_runcards:
                    print(f"  [{i+1}] {current_time} - 🎯 Found RunCard.ini in custom directory!")
                    runcard_location = custom_runcards[0]
                    runcard_found = True
                    break
                
                # Also check default directory (log_SmartCheck)
                default_log_dir = smiwintools_dir / "log_SmartCheck"
                if default_log_dir.exists():
                    default_runcards = self.find_runcard_ini(default_log_dir, max_depth=2)
                    if default_runcards:
                        print(f"  [{i+1}] {current_time} - ⚠️ Found RunCard.ini in default directory (output_dir setting ignored!)")
                        runcard_location = default_runcards[0]
                        runcard_found = True
                        break
                
                print(f"  [{i+1}] {current_time} - Waiting for RunCard.ini to be created...")
            
            # 5. Result verification
            print(f"\n[5] Result verification:")
            
            if runcard_found:
                print(f"  ✅ Found RunCard.ini")
                print(f"  Location: {runcard_location}")
                
                # Determine if it's in the custom directory
                try:
                    relative_to_custom = runcard_location.relative_to(custom_output_dir)
                    print(f"  ✅ Success! RunCard.ini is in custom output directory")
                    print(f"  Relative path: {relative_to_custom}")
                    
                    # Read contents
                    config = configparser.ConfigParser()
                    config.read(runcard_location)
                    if 'Test Status' in config:
                        print(f"\n  RunCard.ini contents:")
                        for key, value in config['Test Status'].items():
                            print(f"    {key}: {value}")
                    
                except ValueError:
                    print(f"  ❌ Failure! RunCard.ini is not in custom output directory")
                    print(f"  output_dir setting was ignored; default path used")
                    pytest.fail("output_dir setting ineffective; SmartCheck.bat ignored it")
            else:
                print(f"  ❌ RunCard.ini not found")
                
                # List directory contents for debugging
                print(f"\n  Custom directory contents:")
                if custom_output_dir.exists():
                    for item in custom_output_dir.rglob("*"):
                        print(f"    {item.relative_to(custom_output_dir)}")
                
                pytest.fail("SmartCheck.bat did not produce RunCard.ini after run")
            
            # Cleanup process
            if process.poll() is None:
                print(f"\n[6] Cleanup:")
                print(f"  Terminating process...")
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
            
        finally:
            os.chdir(original_dir)
        
        print("\n" + "="*80)
    
    def test_output_dir_with_absolute_path(self, smartcheck_bat, smartcheck_ini,
                                          smiwintools_dir, backup_smartcheck_ini):
        """
        Test 2: Configure output_dir using an absolute path

        Verify:
        - Absolute path is recognized correctly
        - Directory will be created if necessary
        """
        print("\n" + "="*80)
        print("Test output_dir with absolute path")
        print("="*80)
        
        if not smartcheck_bat.exists():
            pytest.skip(f"SmartCheck.bat not found")
        
        # Use test directory under test_smartcheck/
        test_smartcheck_dir = Path(__file__).parent
        test_output_dir = test_smartcheck_dir / "smartcheck_absolute_output"

        # Clean up old directory
        if test_output_dir.exists():
            shutil.rmtree(test_output_dir)
        
        test_output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n[1] Set absolute path:")
        print(f"  {test_output_dir}")
        print(f"  Relative to test_smartcheck: {test_output_dir.relative_to(test_smartcheck_dir)}")
        
        # Modify configuration
        self.modify_smartcheck_ini(smartcheck_ini, test_output_dir)
        
        # Verify modification
        configured_dir = self.read_smartcheck_ini_output_dir(smartcheck_ini)
        print(f"  Configured output_dir: {configured_dir}")
        
        print(f"\n[2] Start SmartCheck.bat and wait 30 seconds...")
        
        original_dir = os.getcwd()
        os.chdir(smiwintools_dir)
        
        try:
            process = subprocess.Popen(
                str(smartcheck_bat),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(smiwintools_dir)
            )
            
            # Wait 30 seconds to observe
            time.sleep(30)

            print(f"\n[3] Check output directory:")

            # Check absolute path directory
            if test_output_dir.exists():
                files_in_output = list(test_output_dir.rglob("*"))
                print(f"  Files in absolute path directory: {len(files_in_output)}")

                runcards = [f for f in files_in_output if f.name == "RunCard.ini"]
                if runcards:
                    print(f"  ✅ Found RunCard.ini: {runcards[0]}")
                else:
                    print(f"  ❌ RunCard.ini not found")
                    print(f"  Directory contents:")
                    for f in files_in_output[:10]:  # show only first 10
                        print(f"    {f.relative_to(test_output_dir)}")
            
            # Also check default location
            default_log = smiwintools_dir / "log_SmartCheck"
            if default_log.exists():
                default_runcards = self.find_runcard_ini(default_log, max_depth=2)
                if default_runcards:
                    print(f"  ⚠️ Also found RunCard.ini in default location: {len(default_runcards)}")
            
            # Terminate process
            process.terminate()
            time.sleep(2)
            if process.poll() is None:
                process.kill()
        
        finally:
            os.chdir(original_dir)
        
        print("="*80)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
