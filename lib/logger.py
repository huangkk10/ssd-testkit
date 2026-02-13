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
        
        Example:
            >>> Logger.init_logging()
        """
        if cls._initialized:
            return
        
        # Ensure log directory exists
        if not os.path.exists('./log'):
            os.mkdir('./log')
        
        # Formatter for log messages (includes logger name for module identification)
        formatter = logging.Formatter('[%(levelname)s %(asctime)s] [%(name)s] %(message)s')
        
        # Main logger configuration
        main_logger = logging.getLogger('main')
        
        # Avoid adding handlers multiple times
        if not main_logger.handlers:
            # INFO log file (append mode to preserve all test logs)
            log_filename = "./log/log.txt"
            file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            
            # ERROR log file (append mode to preserve all test logs)
            err_filename = "./log/log.err"
            err_handler = logging.FileHandler(err_filename, mode='a', encoding='utf-8')
            err_handler.setLevel(logging.ERROR)
            err_handler.setFormatter(formatter)
            
            # Console output
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            
            main_logger.addHandler(file_handler)
            main_logger.addHandler(err_handler)
            main_logger.addHandler(console_handler)
            main_logger.setLevel(logging.DEBUG)
        
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