"""
Test Decorators - Provide test step management
"""
import functools
import time
import lib.logger as logger

def step(step_number: int, description: str = ""):
    """
    Test step decorator

    Usage:
        @step(1, "Initialize test environment")
        def test_01_init(self):
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.LogEvt("=" * 60)
            logger.LogEvt(f"Step {step_number}: {description or func.__name__}")
            logger.LogEvt("=" * 60)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.LogEvt(f"[OK] Step {step_number} completed in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.LogErr(f"[FAIL] Step {step_number} failed in {elapsed:.2f}s: {e}")
                raise
        
        return wrapper
    return decorator

def require_reboot_after(delay: int = 10):
    """
    Mark test as requiring reboot

    Usage:
        @require_reboot_after(delay=15)
        def test_03_s3_s4(self):
            # Test logic
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Trigger reboot after test completion
            from framework.test_utils import reboot_system
            reboot_system(delay=delay, reason=f"After {func.__name__}")
            
            return result
        return wrapper
    return decorator
