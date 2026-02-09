import os
import logging
import datetime
import sys

def logConfig():
    logger = logging.getLogger('main')
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return

    # Ensure log directory exists
    if not os.path.exists('./log'):
        os.mkdir('./log')

    # Formatter for log messages
    formatter = logging.Formatter('[%(levelname)s %(asctime)s] %(message)s')

    # Normal log file (append mode to preserve all test logs)
    log_filename = datetime.datetime.now().strftime("./log/log.txt")
    filelogHandler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    filelogHandler.setLevel(logging.INFO)
    filelogHandler.setFormatter(formatter)

    # Error log file (append mode to preserve all test logs)
    log_filename = datetime.datetime.now().strftime("./log/log.err")
    errlogHandler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    errlogHandler.setLevel(logging.ERROR)
    errlogHandler.setFormatter(formatter)

    # Console output
    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(formatter)

    logger.addHandler(filelogHandler)
    logger.addHandler(errlogHandler)
    logger.addHandler(consoleHandler)
    logger.setLevel(logging.DEBUG)

    return

def LogEvt(msg):
    """Log a standard informational event message."""
    try:
        logging.getLogger('main').info(msg)
    except (ValueError, OSError):
        # Ignore errors if file handle is closed
        pass


def LogErr(msg):
    """Log an error message."""
    try:
        logging.getLogger('main').error(msg)
    except (ValueError, OSError):
        pass


def LogWarn(msg):
    """Log a warning message."""
    try:
        logging.getLogger('main').warning(msg)
    except (ValueError, OSError):
        pass


def LogDebug(msg):
    """Log a debug message."""
    try:
        logging.getLogger('main').debug(msg)
    except (ValueError, OSError):
        pass


def LogSection(title):
    """Log a section header (surrounded by separator lines)."""
    logging.getLogger('main').info("")
    logging.getLogger('main').info("=" * 60)
    logging.getLogger('main').info(f"  {title}")
    logging.getLogger('main').info("=" * 60)
    logging.getLogger('main').info("")


def LogStep(step_number, description):
    """Log a test step with its number and description."""
    logging.getLogger('main').info("=" * 60)
    logging.getLogger('main').info(f"[STEP {step_number}] {description}")
    logging.getLogger('main').info("=" * 60)


def LogResult(passed, message):
    """Log the test result as pass or fail with a message."""
    logger = logging.getLogger('main')
    if passed:
        logger.info(f"✓ [PASS] {message}")
    else:
        logger.error(f"✗ [FAIL] {message}")

# Note: logConfig() should be called explicitly after changing to the correct working directory
# Do not call it here at module import time