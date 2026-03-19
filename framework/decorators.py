"""
Test Decorators - Provide test step management
"""
import contextlib
import functools
import inspect
import logging
import time

from lib.logger import log_step_begin, log_step_end

try:
    import allure as _allure

    def _allure_step(title):
        return _allure.step(title)

except ImportError:
    @contextlib.contextmanager
    def _allure_step(title):
        yield


def step(step_number: int, description: str = ""):
    """
    Test step decorator — emits structured step-begin / step-end banners
    and records the step in Allure report when allure-pytest is installed.

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
            step_title = f"[STEP {step_number}] {desc}"
            log_step_begin(lgr, step_number, desc)
            start_time = time.time()
            try:
                with _allure_step(step_title):
                    result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                log_step_end(lgr, step_number, passed=True, elapsed=elapsed)
                return result
            except Exception:
                elapsed = time.time() - start_time
                log_step_end(lgr, step_number, passed=False, elapsed=elapsed)
                raise

        # Explicitly copy the original function's signature so pytest can
        # discover fixture parameters (e.g. `request`) even though the wrapper
        # itself only declares (*args, **kwargs).
        # pytest uses inspect.signature(func, follow_wrapped=False), which does
        # NOT follow __wrapped__ but DOES respect an explicit __signature__.
        wrapper.__signature__ = inspect.signature(func)
        return wrapper
    return decorator

