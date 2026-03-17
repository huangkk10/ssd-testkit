"""
Test Decorators - Provide test step management
"""
import functools
import logging
import time

from lib.logger import log_step_begin, log_step_end


def step(step_number: int, description: str = ""):
    """
    Test step decorator — emits structured step-begin / step-end banners.

    Usage:
        @step(1, "Initialize test environment")
        def test_01_init(self):
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            lgr = logging.getLogger(func.__module__)
            desc = description or func.__name__
            log_step_begin(lgr, step_number, desc)
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                log_step_end(lgr, step_number, passed=True, elapsed=elapsed)
                return result
            except Exception:
                elapsed = time.time() - start_time
                log_step_end(lgr, step_number, passed=False, elapsed=elapsed)
                raise

        return wrapper
    return decorator

