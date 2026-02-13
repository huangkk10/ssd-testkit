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
        
        # Formatter for log messages (includes logger name for module identification)
        formatter = logging.Formatter('[%(levelname)s %(asctime)s] [%(name)s] %(message)s')
        
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
        # Note: We always add our own FileHandlers (log.txt, log.err) even if pytest has its own
        our_log_file = str(log_dir / "log.txt")
        our_err_file = str(log_dir / "log.err")
        
        has_our_log_handler = any(
            isinstance(h, logging.FileHandler) and 
            hasattr(h, 'baseFilename') and 
            Path(h.baseFilename).name == "log.txt"
            for h in root_logger.handlers
        )
        has_our_err_handler = any(
            isinstance(h, logging.FileHandler) and 
            hasattr(h, 'baseFilename') and 
            Path(h.baseFilename).name == "log.err"
            for h in root_logger.handlers
        )
        has_console_handler = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers)
        
        # Debug: print handler info
        if not has_our_log_handler:
            print(f"[Logger Debug] Adding log.txt handler to {log_dir}")
        else:
            print(f"[Logger Debug] log.txt handler already exists")
            
        if not has_our_err_handler:
            print(f"[Logger Debug] Adding log.err handler to {log_dir}")
        else:
            print(f"[Logger Debug] log.err handler already exists")
        
        if not has_our_log_handler:
            # INFO log file (append mode to preserve all test logs)
            file_handler = logging.FileHandler(our_log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            
            root_logger.addHandler(file_handler)
        
        if not has_our_err_handler:
            # ERROR log file (append mode to preserve all test logs)
            err_handler = logging.FileHandler(our_err_file, mode='a', encoding='utf-8')
            err_handler.setLevel(logging.ERROR)
            err_handler.setFormatter(formatter)
            
            root_logger.addHandler(err_handler)
        
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


# Note: Logger initialization happens automatically when getting a logger
# Legacy code can still call logConfig() explicitly for backward compatibility