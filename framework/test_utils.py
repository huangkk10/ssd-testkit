"""
Common test utility functions
"""
import shutil
from pathlib import Path
import subprocess
import time

# ========== Environment Management ==========
def setup_test_environment(log_path: str):
    """Initialize test environment"""
    # Clean old logs
    if Path(log_path).exists():
        shutil.rmtree(log_path)
    
    # Create log directory
    Path(log_path).mkdir(parents=True, exist_ok=True)
    print(f"[TestUtils] Test environment initialized: {log_path}")

def cleanup_test_environment():
    """Clean up test environment"""
    print("[TestUtils] Test environment cleaned up")

# ========== Reboot Related ==========
def need_reboot() -> bool:
    """Check if reboot is needed (example implementation)"""
    # Can implement logic based on actual needs
    return False

def reboot_system(delay: int = 10, reason: str = "Test requires reboot", test_file: str = None):
    """
    Convenience function for system reboot
    
    Usage:
        from framework.test_utils import reboot_system
        reboot_system(delay=10, reason="After S3/S4 test", test_file=__file__)
    
    Args:
        delay: Reboot delay time (seconds)
        reason: Reboot reason
        test_file: Current test file path (for recovery after reboot)
    """
    from framework.reboot_manager import RebootManager
    
    print(f"\n[Reboot] {reason}")
    mgr = RebootManager()
    mgr.setup_reboot(delay=delay, reason=reason, test_file=test_file)

# ========== Tool Execution ==========
def run_tool_with_retry(tool_func, max_retry: int = 3, retry_delay: int = 5):
    """
    Tool execution with retry mechanism
    
    Args:
        tool_func: Tool function
        max_retry: Maximum retry count
        retry_delay: Retry delay (seconds)
    
    Returns:
        Execution result
    """
    for attempt in range(max_retry):
        try:
            result = tool_func()
            return result
        except Exception as e:
            print(f"[Retry] Attempt {attempt + 1} failed: {e}")
            if attempt < max_retry - 1:
                time.sleep(retry_delay)
            else:
                raise

# ========== Directory Management ==========
def cleanup_directory(path: str, description: str = "directory", logger=None):
    """
    Common directory cleanup: delete and recreate
    
    Args:
        path: Directory path
        description: Directory description (for logging)
        logger: Optional logger object (uses print if not provided)
    
    Example:
        from framework.test_utils import cleanup_directory
        cleanup_directory('./testlog/CDI', 'CDI log directory', logger)
    """
    path_obj = Path(path)
    log = logger.info if logger else print
    
    if path_obj.exists():
        log(f"[TestUtils] Removing old {description}: {path_obj}")
        shutil.rmtree(path_obj)
    
    path_obj.mkdir(parents=True, exist_ok=True)
    log(f"[TestUtils] Created clean {description}: {path_obj}")

# ========== File Operations ==========
def ensure_file_exists(file_path: str, timeout: int = 30) -> bool:
    """
    Wait for file generation
    
    Args:
        file_path: File path
        timeout: Timeout (seconds)
    
    Returns:
        Whether file exists
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if Path(file_path).exists():
            return True
        time.sleep(1)
    return False
