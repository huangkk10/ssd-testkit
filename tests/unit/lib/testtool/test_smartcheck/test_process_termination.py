"""
Test script to verify SmartCheck process termination works correctly.

This script specifically tests that:
1. SmartCheck.bat and all child processes are terminated
2. No orphaned processes remain after stop_smartcheck_bat()
"""

import pytest
import time
import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from lib.testtool.smartcheck import SmartCheckController


def get_process_tree(pid):
    """
    Get all child processes of a given PID.
    
    Returns list of (pid, name) tuples.
    """
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', f'ParentProcessId={pid}', 
             'get', 'ProcessId,Name'],
            capture_output=True,
            timeout=5,
            text=True
        )
        
        processes = []
        for line in result.stdout.split('\n')[1:]:  # Skip header
            line = line.strip()
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        child_pid = int(parts[-1])
                        name = ' '.join(parts[:-1])
                        processes.append((child_pid, name))
                    except ValueError:
                        pass
        
        return processes
    except Exception as e:
        print(f"Error getting process tree: {e}")
        return []


def process_exists(pid):
    """Check if a process with given PID exists."""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}'],
            capture_output=True,
            timeout=2,
            text=True
        )
        return str(pid) in result.stdout
    except Exception:
        return False


@pytest.mark.real_bat
class TestProcessTermination:
    """Test process termination functionality."""
    
    @pytest.fixture
    def real_paths(self):
        """Get real SmartCheck.bat paths."""
        base_path = Path(__file__).parent.parent / "bin" / "SmiWinTools"
        bat_path = base_path / "SmartCheck.bat"
        ini_path = base_path / "SmartCheck.ini"
        output_dir = base_path / "test_termination_output"
        
        if not bat_path.exists():
            pytest.skip(f"SmartCheck.bat not found at {bat_path}")
        
        output_dir.mkdir(exist_ok=True)
        
        yield {
            'bat_path': str(bat_path),
            'ini_path': str(ini_path),
            'output_dir': str(output_dir),
        }
        
        # Cleanup
        import shutil
        if output_dir.exists():
            try:
                shutil.rmtree(output_dir)
            except Exception as e:
                print(f"Cleanup warning: {e}")
    
    def test_process_termination_complete(self, real_paths):
        """
        Test that stop_smartcheck_bat terminates all processes.
        
        This test:
        1. Starts SmartCheck.bat
        2. Records the parent PID and any child PIDs
        3. Calls stop_smartcheck_bat()
        4. Verifies all processes are terminated
        """
        controller = SmartCheckController(
            bat_path=real_paths['bat_path'],
            cfg_ini_path=real_paths['ini_path'],
            output_dir=real_paths['output_dir']
        )
        
        # Configure for test
        controller.set_config(
            total_time=10,
            dut_id="0",
            timeout=10
        )
        
        print("\n=== Starting SmartCheck ===")
        controller.start()
        
        # Wait for process to fully start
        time.sleep(5)
        
        # Get the parent PID
        parent_pid = controller._process.pid if controller._process else None
        assert parent_pid is not None, "Process should have been started"
        
        print(f"Parent PID: {parent_pid}")
        
        # Get child processes
        children_before = get_process_tree(parent_pid)
        print(f"Child processes before stop: {children_before}")
        
        # Collect all PIDs to check
        all_pids = [parent_pid] + [pid for pid, _ in children_before]
        print(f"All PIDs to terminate: {all_pids}")
        
        # Verify parent is running
        assert process_exists(parent_pid), f"Parent process {parent_pid} should be running"
        
        print("\n=== Stopping SmartCheck ===")
        controller.stop()
        
        # Wait for termination to complete
        controller.join(timeout=30)
        
        # Wait a bit more for cleanup
        time.sleep(2)
        
        print("\n=== Verifying termination ===")
        
        # Check if any processes still exist
        surviving_processes = []
        for pid in all_pids:
            if process_exists(pid):
                surviving_processes.append(pid)
                print(f"WARNING: Process {pid} still exists!")
            else:
                print(f"✓ Process {pid} terminated")
        
        # Verify all processes are terminated
        if surviving_processes:
            print(f"\n❌ FAILED: {len(surviving_processes)} processes still running: {surviving_processes}")
            
            # Try to get process names
            for pid in surviving_processes:
                try:
                    result = subprocess.run(
                        ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'LIST'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    print(f"Process {pid} info:\n{result.stdout}")
                except Exception as e:
                    print(f"Could not get info for {pid}: {e}")
            
            assert False, f"Process termination incomplete: {len(surviving_processes)} processes still running"
        else:
            print(f"\n✓ SUCCESS: All {len(all_pids)} processes terminated")
    
    def test_process_termination_quick(self, real_paths):
        """
        Test quick start/stop cycle.
        
        Ensures termination works even if SmartCheck hasn't fully initialized.
        """
        controller = SmartCheckController(
            bat_path=real_paths['bat_path'],
            cfg_ini_path=real_paths['ini_path'],
            output_dir=real_paths['output_dir']
        )
        
        controller.set_config(total_time=10, dut_id="0", timeout=10)
        
        print("\n=== Quick start/stop test ===")
        controller.start()
        
        # Stop almost immediately
        time.sleep(2)
        
        parent_pid = controller._process.pid if controller._process else None
        print(f"Parent PID: {parent_pid}")
        
        controller.stop()
        controller.join(timeout=30)
        
        # Verify termination
        time.sleep(1)
        
        if parent_pid and process_exists(parent_pid):
            print(f"❌ Parent process {parent_pid} still exists")
            assert False, "Process should be terminated"
        else:
            print(f"✓ Process terminated successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "real_bat"])
