"""
Allure metadata helpers — bridge between log_phase / log_table and Allure labels.

These functions are safe to call even when allure-pytest is NOT installed;
the allure-specific parts are silently skipped.
"""
import logging

try:
    import allure as _allure
    _ALLURE_AVAILABLE = True
except ImportError:
    _ALLURE_AVAILABLE = False


def allure_phase(lgr: logging.Logger, phase_name: str) -> None:
    """Write a phase banner to the log AND mark the current Allure feature.

    Drop-in replacement for ``log_phase()`` when Allure integration is desired.

    Usage (identical to log_phase):
        from lib.allure_helper import allure_phase
        allure_phase(logger, "PRE-REBOOT")
    """
    from lib.logger import log_phase
    log_phase(lgr, phase_name)
    if _ALLURE_AVAILABLE:
        _allure.dynamic.feature(phase_name)
