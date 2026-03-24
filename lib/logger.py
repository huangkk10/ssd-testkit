"""
Enhanced Logger Module with OOP Interface

This module provides both legacy function-based logging and modern OOP logging interface.

Legacy usage (backward compatible):
    from lib.logger import logConfig, LogEvt, LogErr
    logConfig()
    LogEvt("Information message")
    LogErr("Error message")

Modern usage (recommended):
    from lib.logger import get_module_logger
    logger = get_module_logger(__name__)
    logger.info("Information message")
    logger.error("Error message")

Standard Python logging (also supported):
    import logging
    from lib.logger import Logger
    Logger.init_logging()
    logger = logging.getLogger(__name__)
    logger.info("Information message")
"""

import os
import logging
import datetime
import sys
import traceback
from typing import Optional, Dict
from pathlib import Path

# Global variable to store log directory (will be set at init time)
_LOG_DIR = None

def _get_log_dir() -> Path:
    """
    Get log directory path dynamically.
    - In packaged environment: use path_manager
    - In development: use relative path (supports os.chdir)
    """
    global _LOG_DIR
    
    # Try to import path_manager for packaged environment
    try:
        from path_manager import path_manager
        return path_manager.get_log_dir()
    except ImportError:
        # In development: use relative path (recalculated each time)
        log_dir = Path('./log')
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir


class BriefFormatter(logging.Formatter):
    """Log4j-style formatter: date + fixed-width level + short module name + func:line.

    Output format:
        2026-03-17 10:23:01.456 INFO  test_main      test_01_precondition : 45 - message
    """

    def formatTime(self, record, datefmt=None):
        ct = datetime.datetime.fromtimestamp(record.created)
        return ct.strftime('%Y-%m-%d %H:%M:%S.') + f'{ct.microsecond // 1000:03d}'

    def format(self, record):
        parts = record.name.split('.')
        record.short_name = '.'.join(parts[-2:]) if len(parts) >= 2 else record.name
        return super().format(record)


def _write_session_header(log_file: str) -> None:
    """Write a session start banner to a log file (called when a new handler is created)."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    header = (
        '\n' +
        '=' * 80 + '\n' +
        f'  SESSION START: {now}\n' +
        '=' * 80 + '\n'
    )
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(header)
    except Exception:
        pass


class Logger:
    """
    Object-oriented logger wrapper with centralized configuration.
    
    This class provides:
    - Centralized logging configuration
    - Module-specific logger instances
    - File and console output management
    - Thread-safe initialization
    
    Example:
        >>> # Initialize logging system
        >>> Logger.init_logging()
        >>> 
        >>> # Get logger for specific module
        >>> logger = Logger.get_logger(__name__)
        >>> logger.info("Information message")
        >>> logger.error("Error message")
    """
    
    _initialized = False
    _loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def get_logger(cls, name: str = 'main') -> logging.Logger:
        """
        Get or create a logger instance for the specified name.
        
        Args:
            name: Logger name (typically __name__ for module-specific logging)
        
        Returns:
            logging.Logger: Configured logger instance
        
        Example:
            >>> logger = Logger.get_logger(__name__)
            >>> logger.info("Message from this module")
        """
        if not cls._initialized:
            cls.init_logging()
        
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        
        return cls._loggers[name]
    
    @classmethod
    def init_logging(cls) -> None:
        """
        Initialize logging configuration (idempotent - safe to call multiple times).
        
        Sets up:
        - Log directory creation
        - File handlers for INFO and ERROR levels
        - Console handler for INFO level
        - Common formatter with timestamp
        
        Note: When working directory changes (e.g., in tests), file handlers
        will be recreated to write to the new location.
        
        Example:
            >>> Logger.init_logging()
        """
        # Get log directory (dynamically calculated based on current working directory)
        log_dir = _get_log_dir()
        log_dir_abs = log_dir.resolve()  # Get absolute path for comparison
        
        # Log4j-style formatter: date + level + short module + func:line
        formatter = BriefFormatter(
            fmt='%(asctime)s %(levelname)-5s %(short_name)-14s %(funcName)-20s:%(lineno)3d - %(message)s'
        )
        
        # Configure root logger (so all child loggers inherit handlers)
        root_logger = logging.getLogger()
        
        # Remove existing file handlers if log directory changed
        # (This handles the case where os.chdir() changes working directory)
        handlers_to_remove = []
        for handler in root_logger.handlers[:]:  # Use slice to iterate over copy
            if isinstance(handler, logging.FileHandler):
                try:
                    # Check if handler's file is in a different directory
                    handler_path = Path(handler.baseFilename)
                    handler_dir_abs = handler_path.resolve().parent
                    if handler_dir_abs != log_dir_abs:
                        handlers_to_remove.append(handler)
                except Exception:
                    # If we can't determine the path, remove the handler to be safe
                    handlers_to_remove.append(handler)
        
        for handler in handlers_to_remove:
            try:
                handler.close()
                root_logger.removeHandler(handler)
            except Exception:
                pass  # Ignore errors during handler removal
        
        # Check if we need to add file handlers
        our_log_file = str(log_dir / "app.log")
        our_err_file = str(log_dir / "error.log")

        has_our_log_handler = any(
            isinstance(h, logging.FileHandler) and
            hasattr(h, 'baseFilename') and
            Path(h.baseFilename).name == "app.log"
            for h in root_logger.handlers
        )
        has_our_err_handler = any(
            isinstance(h, logging.FileHandler) and
            hasattr(h, 'baseFilename') and
            Path(h.baseFilename).name == "error.log"
            for h in root_logger.handlers
        )
        has_console_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in root_logger.handlers
        )

        if not has_our_log_handler:
            # Log file level: controlled by LOG_LEVEL env var (default DEBUG).
            _log_level = getattr(logging, os.getenv('LOG_LEVEL', 'DEBUG').upper(), logging.DEBUG)
            file_handler = logging.FileHandler(our_log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(_log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            _write_session_header(our_log_file)

        if not has_our_err_handler:
            # ERROR log file (append mode to preserve all test logs)
            err_handler = logging.FileHandler(our_err_file, mode='a', encoding='utf-8')
            err_handler.setLevel(logging.ERROR)
            err_handler.setFormatter(formatter)
            root_logger.addHandler(err_handler)
            _write_session_header(our_err_file)
        
        if not has_console_handler:
            # Console output
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        root_logger.setLevel(logging.DEBUG)
        cls._initialized = True


# ============================================================================
# Modern API (Recommended for new code)
# ============================================================================

def get_module_logger(module_name: str = 'main') -> logging.Logger:
    """
    Get a logger instance for the specified module (recommended approach).
    
    This is the preferred way to get loggers in new code as it provides:
    - Module-specific log identification
    - Standard Python logging interface
    - Easy integration with testing frameworks
    
    Args:
        module_name: Module name (use __name__ for automatic module detection)
    
    Returns:
        logging.Logger: Configured logger instance
    
    Example:
        >>> from lib.logger import get_module_logger
        >>> logger = get_module_logger(__name__)
        >>> logger.info("Starting process...")
        >>> logger.error("Process failed")
        >>> logger.warning("Process slow")
        >>> logger.debug("Debug info")
    """
    return Logger.get_logger(module_name)


# ============================================================================
# Legacy API (Backward Compatible - preserves existing functionality)
# ============================================================================

def logConfig():
    """
    Initialize logging configuration (legacy function - backward compatible).
    
    This function is maintained for backward compatibility with existing code.
    New code should use Logger.init_logging() or simply call get_module_logger().
    
    Example:
        >>> logConfig()  # Initialize logging
    """
    Logger.init_logging()


def LogEvt(msg):
    """
    Log a standard informational event message (legacy function).
    
    Backward compatible function. New code should use:
        logger.info(msg)
    
    Args:
        msg: Message to log
    
    Example:
        >>> LogEvt("Process started")
    """
    try:
        Logger.get_logger('main').info(msg)
    except (ValueError, OSError):
        # Ignore errors if file handle is closed
        pass


def LogErr(msg):
    """
    Log an error message (legacy function).
    
    Backward compatible function. New code should use:
        logger.error(msg)
    
    Args:
        msg: Error message to log
    
    Example:
        >>> LogErr("Process failed")
    """
    try:
        Logger.get_logger('main').error(msg)
    except (ValueError, OSError):
        pass


def LogWarn(msg):
    """
    Log a warning message (legacy function).
    
    Backward compatible function. New code should use:
        logger.warning(msg)
    
    Args:
        msg: Warning message to log
    
    Example:
        >>> LogWarn("Process is slow")
    """
    try:
        Logger.get_logger('main').warning(msg)
    except (ValueError, OSError):
        pass


def LogDebug(msg):
    """
    Log a debug message (legacy function).
    
    Backward compatible function. New code should use:
        logger.debug(msg)
    
    Args:
        msg: Debug message to log
    
    Example:
        >>> LogDebug("Variable value: 123")
    """
    try:
        Logger.get_logger('main').debug(msg)
    except (ValueError, OSError):
        pass


def LogSection(title):
    """
    Log a section header surrounded by separator lines (legacy function).
    
    Args:
        title: Section title
    
    Example:
        >>> LogSection("Configuration Phase")
    """
    logger = Logger.get_logger('main')
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  {title}")
    logger.info("=" * 60)
    logger.info("")


def LogStep(step_number, description):
    """
    Log a test step with its number and description (legacy function).
    
    Args:
        step_number: Step number
        description: Step description
    
    Example:
        >>> LogStep(1, "Initialize system")
    """
    logger = Logger.get_logger('main')
    logger.info("=" * 60)
    logger.info(f"[STEP {step_number}] {description}")
    logger.info("=" * 60)


def LogResult(passed, message):
    """
    Log the test result as pass or fail with a message (legacy function).
    
    Args:
        passed: True if test passed, False if failed
        message: Result message
    
    Example:
        >>> LogResult(True, "System initialized")
        >>> LogResult(False, "Initialization failed")
    """
    logger = Logger.get_logger('main')
    if passed:
        logger.info(f"✓ [PASS] {message}")
    else:
        logger.error(f"✗ [FAIL] {message}")


def clear_log_files() -> None:
    """
    Delete the logger's own log files (app.log and error.log) so that the next
    test run starts with a clean log.

    On Windows, FileHandler keeps the file open as long as the handler exists,
    so this function first closes and removes all FileHandlers that point to
    these files, deletes the files, then re-initializes logging so that fresh
    handlers (and fresh files) are created for subsequent log calls.

    Usage:
        from lib.logger import clear_log_files
        clear_log_files()

    Raises:
        Nothing — failures are printed as warnings so test execution continues.
    """
    log_dir = _get_log_dir()
    target_names = {'app.log', 'error.log'}

    # ── Step 1: close and detach FileHandlers that own these files ────────────
    root_logger = logging.getLogger()
    handlers_to_remove = []
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            try:
                if Path(handler.baseFilename).name in target_names:
                    handlers_to_remove.append(handler)
            except Exception:
                pass

    for handler in handlers_to_remove:
        try:
            handler.close()
            root_logger.removeHandler(handler)
        except Exception:
            pass

    # Also reset Logger._initialized so init_logging() will recreate handlers
    Logger._initialized = False

    # ── Step 2: delete the files (handles are now released) ───────────────────
    # On Windows, FileHandler.close() may not immediately release the OS lock,
    # so unlink() can fail with PermissionError.  Fall back to truncation ('w'
    # mode) which works even on a still-open file, so the next init_logging()
    # call opens a fresh, empty file rather than appending to the old content.
    for filename in target_names:
        log_file = log_dir / filename
        if log_file.exists():
            try:
                log_file.unlink()
            except Exception:
                # unlink failed (Windows file lock) — truncate as fallback
                try:
                    with open(log_file, 'w'):
                        pass
                except Exception as exc2:
                    print(f'[Logger] WARNING: Could not clear {log_file}: {exc2}')

    # ── Step 3: re-initialize so subsequent log calls work normally ───────────
    Logger.init_logging()


# Note: Logger initialization happens automatically when getting a logger
# Legacy code can still call logConfig() explicitly for backward compatibility


# ============================================================================
# Structured Log Helper Functions (P2 — Modern API)
# ============================================================================

_STEP_SEP = '─' * 60
_PHASE_SEP = '━' * 60


def log_step_begin(lgr: logging.Logger, step_no: int, desc: str,
                   total: int = 0, phase: str = '') -> None:
    """Output a step-start banner to the log.

    Example output:
        ────────────────────────────────────────────────────────────
          [STEP 1/9] Precondition — cleanup and create log directories | Phase: PRE-REBOOT
        ────────────────────────────────────────────────────────────
    """
    total_str = f'/{total}' if total else ''
    phase_str = f' | Phase: {phase}' if phase else ''
    lgr.info(_STEP_SEP)
    lgr.info(f'  [STEP {step_no}{total_str}] {desc}{phase_str}')
    lgr.info(_STEP_SEP)


def log_step_end(lgr: logging.Logger, step_no: int, passed: bool,
                 elapsed: float, total: int = 0) -> None:
    """Output a step-end summary (PASS/FAIL + elapsed time) to the log.

    Example output:
          [STEP 1/9] PASS  |  Elapsed: 2.7s
        ────────────────────────────────────────────────────────────
    """
    status = 'PASS' if passed else 'FAIL'
    total_str = f'/{total}' if total else ''
    lgr.info(f'  [STEP {step_no}{total_str}] {status}  |  Elapsed: {elapsed:.1f}s')
    lgr.info(_STEP_SEP)


def log_kv(lgr: logging.Logger, label: str, value, unit: str = '') -> None:
    """Log a key-value metric in aligned format.

    Example output:
          SW DRIPS                       = 85.3 %
          HW DRIPS                       = 91.2 %
    """
    unit_str = f' {unit}' if unit else ''
    lgr.info(f'  {label:<30} = {value}{unit_str}')


def log_table(lgr: logging.Logger, headers: list, rows: list) -> None:
    """Log a structured ASCII table.

    Example output:
        ┌──────────┬───────────┬───────────┬──────┐
        │ Session  │ SW DRIPS  │ HW DRIPS  │ PASS │
        ├──────────┼───────────┼───────────┼──────┤
        │ 1        │ 85.3%     │ 91.2%     │ PASS │
        │ 2        │ 78.1%     │ 82.0%     │ FAIL │
        └──────────┴───────────┴───────────┴──────┘
    """
    if not rows:
        return
    col_widths = [
        max(len(str(h)), max((len(str(row[i])) for row in rows), default=0))
        for i, h in enumerate(headers)
    ]

    def _row_line(cells):
        return '│ ' + ' │ '.join(str(c).ljust(col_widths[i]) for i, c in enumerate(cells)) + ' │'

    def _sep_line(left, mid, right):
        return left + mid.join('─' * (w + 2) for w in col_widths) + right

    lgr.info(_sep_line('┌', '┬', '┐'))
    lgr.info(_row_line(headers))
    lgr.info(_sep_line('├', '┼', '┤'))
    for row in rows:
        lgr.info(_row_line(row))
    lgr.info(_sep_line('└', '┴', '┘'))


def log_exception(lgr: logging.Logger, msg: str, exc: Exception,
                  context: dict = None) -> None:
    """Log an exception with optional context dict, including full traceback.

    Designed to be called from within an ``except`` block so that
    ``traceback.format_exc()`` captures the active exception.

    Example usage:
        try:
            ctrl.install()
        except Exception as e:
            log_exception(logger, "PHM install failed", e,
                          context={"install_path": cfg["install_path"], "step": "TEST_02"})
            raise
    """
    lgr.error(f'{msg}: {type(exc).__name__}: {exc}')
    if context:
        for k, v in context.items():
            lgr.error(f'  Context [{k}] = {v}')
    tb = traceback.format_exc()
    if tb and tb.strip() not in ('NoneType: None', 'None'):
        for line in tb.rstrip().splitlines():
            lgr.error(f'  {line}')


def log_phase(lgr: logging.Logger, phase_name: str) -> None:
    """Log a phase transition banner (e.g. PRE-REBOOT / POST-REBOOT).

    Example output:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          Phase: PRE-REBOOT
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    lgr.info('')
    lgr.info(_PHASE_SEP)
    lgr.info(f'  Phase: {phase_name}')
    lgr.info(_PHASE_SEP)
    lgr.info('')