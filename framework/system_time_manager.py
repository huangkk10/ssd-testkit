"""
System Time Manager

Manages system time save/restore for tests that modify the system clock.
This is useful for aging tests or other scenarios where system time is temporarily changed.

Features:
- Save original system time before modification
- Restore system time after test completion
- State persistence across test runs
- PowerShell-based time setting (requires admin)
- Automatic cleanup

Usage:
    from framework.system_time_manager import SystemTimeManager
    
    # In test setup
    time_mgr = SystemTimeManager()
    time_mgr.save_original_time()
    
    # Modify system time (e.g., using external tool)
    # ...
    
    # In test teardown
    time_mgr.restore_original_time()
"""

import datetime
import subprocess
import json
import os
from pathlib import Path


class SystemTimeManager:
    """
    Manage system time save/restore for tests that modify system clock
    
    This class provides a safe way to save the current system time,
    modify it during testing, and restore it afterwards.
    
    Attributes:
        state_file (Path): Path to JSON state file storing original time
        original_time (str): ISO format timestamp of original time
    """
    
    def __init__(self, state_file="system_time_state.json"):
        """
        Initialize SystemTimeManager
        
        Args:
            state_file (str): Path to state file. Default: "system_time_state.json"
        """
        self.state_file = Path(state_file)
        self.original_time = None
    
    def save_original_time(self):
        """
        Save current system time if not already saved
        
        This method is idempotent - if a saved time already exists,
        it will not overwrite it. This prevents accidentally losing
        the original time if called multiple times.
        
        Returns:
            bool: True if time was saved, False if already exists
        """
        # Check if original time already saved
        existing_time = self._load_state()
        if existing_time:
            print(f"[SystemTimeManager] Original time already saved: {existing_time}")
            self.original_time = existing_time
            return False
        
        # Save current time
        self.original_time = datetime.datetime.now().isoformat()
        self._save_state(self.original_time)
        print(f"[SystemTimeManager] Saved original time: {self.original_time}")
        return True
    
    def restore_original_time(self):
        """
        Restore system time to original value
        
        Uses PowerShell Set-Date command to restore the system clock.
        Requires administrator privileges.
        
        Returns:
            bool: True if restoration successful, False otherwise
        """
        original = self._load_state()
        if not original:
            print("[SystemTimeManager] No original time to restore")
            return False
        
        print(f"[SystemTimeManager] Restoring system time to {original}")
        
        try:
            # Use PowerShell Set-Date to restore the system time
            result = subprocess.run(
                ["powershell", "-Command", f"Set-Date -Date \"{original}\""],
                check=False,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"[SystemTimeManager] Successfully restored time to {original}")
                self._clear_state()
                return True
            else:
                print(f"[SystemTimeManager] Failed to restore time:")
                print(f"  Return code: {result.returncode}")
                print(f"  Stdout: {result.stdout}")
                print(f"  Stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("[SystemTimeManager] Timeout while restoring system time")
            return False
        except Exception as e:
            print(f"[SystemTimeManager] Error restoring time: {e}")
            return False
    
    def get_original_time(self):
        """
        Get the saved original time without restoring it
        
        Returns:
            str: ISO format timestamp, or None if not saved
        """
        return self._load_state()
    
    def clear_saved_time(self):
        """
        Clear saved time without restoring
        
        Use this if you manually restored the time or want to reset.
        
        Returns:
            bool: True if state was cleared, False if no state existed
        """
        if self.state_file.exists():
            self._clear_state()
            print("[SystemTimeManager] Cleared saved time state")
            return True
        return False
    
    def _save_state(self, time_str):
        """
        Save state to JSON file with fsync
        
        Args:
            time_str (str): ISO format timestamp to save
        """
        state = {
            "original_time": time_str,
            "saved_at": datetime.datetime.now().isoformat()
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure written to disk
    
    def _load_state(self):
        """
        Load original time from state file
        
        Returns:
            str: Original time if exists, None otherwise
        """
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file) as f:
                state = json.load(f)
                return state.get("original_time")
        except (json.JSONDecodeError, OSError) as e:
            print(f"[SystemTimeManager] Error loading state: {e}")
            return None
    
    def _clear_state(self):
        """
        Delete state file
        """
        if self.state_file.exists():
            try:
                os.remove(self.state_file)
            except OSError as e:
                print(f"[SystemTimeManager] Error deleting state file: {e}")


# Convenience functions
def save_system_time(state_file="system_time_state.json"):
    """
    Convenience function to save system time
    
    Args:
        state_file (str): Path to state file
        
    Returns:
        SystemTimeManager: Manager instance
    """
    mgr = SystemTimeManager(state_file)
    mgr.save_original_time()
    return mgr


def restore_system_time(state_file="system_time_state.json"):
    """
    Convenience function to restore system time
    
    Args:
        state_file (str): Path to state file
        
    Returns:
        bool: True if restoration successful
    """
    mgr = SystemTimeManager(state_file)
    return mgr.restore_original_time()


if __name__ == "__main__":
    # Test SystemTimeManager
    print("Testing SystemTimeManager...")
    
    mgr = SystemTimeManager("test_time_state.json")
    
    # Save current time
    print("\n1. Saving current time...")
    mgr.save_original_time()
    
    # Check saved time
    print("\n2. Checking saved time...")
    original = mgr.get_original_time()
    print(f"   Saved time: {original}")
    
    # Try to save again (should not overwrite)
    print("\n3. Trying to save again (should skip)...")
    mgr.save_original_time()
    
    # Simulate time change (not actually changing system time in test)
    print("\n4. (Simulating time change...)")
    print("   In real test, system time would be modified here")
    
    # Restore time
    print("\n5. Restoring time...")
    success = mgr.restore_original_time()
    print(f"   Restore successful: {success}")
    
    # Cleanup test file
    if Path("test_time_state.json").exists():
        os.remove("test_time_state.json")
    
    print("\n✓ SystemTimeManager test complete")
