"""
SmartCheck Controller Usage Example

This example demonstrates how to use the SmartCheckController class
to run SmartCheck.bat in a threaded environment.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.testtool.smartcheck import SmartCheckController


def example_basic_usage():
    """
    Basic usage example: Run SmartCheck with default settings.
    """
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)
    
    # Define paths (relative to this script)
    test_dir = Path(__file__).parent.parent / "tests" / "unit" / "lib" / "testtool"
    bat_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.bat")
    cfg_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.ini")
    output_dir = str(test_dir / "test_smartcheck" / "example_output")
    
    # Create controller
    controller = SmartCheckController(
        bat_path=bat_path,
        cfg_ini_path=cfg_path,
        output_dir=output_dir
    )
    
    # Configure parameters
    controller.set_config(
        total_time=5,      # Run for 5 minutes
        dut_id="0",        # DUT ID
        timeout=180,       # 3 minute timeout (includes startup time)
        check_interval=3   # Check every 3 seconds
    )
    
    # Start the thread
    print(f"Starting SmartCheck...")
    controller.start()
    
    # Wait for completion (with timeout)
    controller.join(timeout=200)
    
    # Check result
    if controller.status:
        print("✓ SmartCheck completed successfully")
    else:
        print("✗ SmartCheck failed or timed out")
    
    return controller.status


def example_with_monitoring():
    """
    Example with real-time monitoring of thread status.
    """
    print("\n" + "=" * 60)
    print("Example 2: With Real-time Monitoring")
    print("=" * 60)
    
    # Define paths
    test_dir = Path(__file__).parent.parent / "tests" / "unit" / "lib" / "testtool"
    bat_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.bat")
    cfg_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.ini")
    output_dir = str(test_dir / "test_smartcheck" / "example_monitored_output")
    
    # Create and configure controller
    controller = SmartCheckController(
        bat_path=bat_path,
        cfg_ini_path=cfg_path,
        output_dir=output_dir
    )
    controller.set_config(total_time=5, dut_id="0", timeout=180)
    
    # Start
    print("Starting SmartCheck with monitoring...")
    controller.start()
    
    # Monitor while running
    start_time = time.time()
    while controller.is_alive():
        elapsed = time.time() - start_time
        print(f"  Running... {elapsed:.1f}s elapsed (Status: {controller.status})")
        time.sleep(5)  # Print status every 5 seconds
        
        # Allow early exit if needed
        if elapsed > 200:
            print("  Timeout reached, stopping...")
            controller.stop()
            break
    
    # Final result
    print(f"\nFinal status: {'✓ Success' if controller.status else '✗ Failed'}")
    return controller.status


def example_early_stop():
    """
    Example demonstrating early stop functionality.
    """
    print("\n" + "=" * 60)
    print("Example 3: Early Stop")
    print("=" * 60)
    
    # Define paths
    test_dir = Path(__file__).parent.parent / "tests" / "unit" / "lib" / "testtool"
    bat_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.bat")
    cfg_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.ini")
    output_dir = str(test_dir / "test_smartcheck" / "example_early_stop")
    
    # Create controller
    controller = SmartCheckController(
        bat_path=bat_path,
        cfg_ini_path=cfg_path,
        output_dir=output_dir
    )
    controller.set_config(total_time=60, dut_id="0", timeout=300)
    
    # Start
    print("Starting SmartCheck (will stop after 30 seconds)...")
    controller.start()
    
    # Wait 30 seconds then stop
    time.sleep(30)
    print("Requesting early stop...")
    controller.stop()
    
    # Wait for cleanup
    controller.join(timeout=10)
    
    print(f"Stopped after 30 seconds (Status: {controller.status})")
    return True


def example_concurrent_tests():
    """
    Example running multiple SmartCheck instances concurrently.
    """
    print("\n" + "=" * 60)
    print("Example 4: Concurrent Execution")
    print("=" * 60)
    
    # This would require multiple DUT or different configurations
    # For demonstration, we'll show the pattern
    
    test_dir = Path(__file__).parent.parent / "tests" / "unit" / "lib" / "testtool"
    bat_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.bat")
    cfg_path = str(test_dir / "bin" / "SmiWinTools" / "SmartCheck.ini")
    
    # Create multiple controllers with different output directories
    controllers = []
    for i in range(2):
        output_dir = str(test_dir / "test_smartcheck" / f"example_concurrent_{i}")
        controller = SmartCheckController(
            bat_path=bat_path,
            cfg_ini_path=cfg_path,
            output_dir=output_dir
        )
        controller.set_config(
            total_time=5,
            dut_id=str(i),
            timeout=180
        )
        controllers.append(controller)
    
    # Start all controllers
    print(f"Starting {len(controllers)} SmartCheck instances...")
    for i, ctrl in enumerate(controllers):
        ctrl.start()
        print(f"  Started instance {i}")
    
    # Wait for all to complete
    print("Waiting for all instances to complete...")
    for i, ctrl in enumerate(controllers):
        ctrl.join(timeout=200)
        print(f"  Instance {i} finished: {ctrl.status}")
    
    # Check results
    all_passed = all(ctrl.status for ctrl in controllers)
    print(f"\nAll tests passed: {all_passed}")
    return all_passed


if __name__ == "__main__":
    print("SmartCheck Controller Usage Examples")
    print("=" * 60)
    
    try:
        # Run examples
        example_basic_usage()
        # example_with_monitoring()
        # example_early_stop()
        # example_concurrent_tests()
        
        print("\n" + "=" * 60)
        print("Examples completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
