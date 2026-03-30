"""
OsConfig Actions — Internal Helpers

Low-level subprocess utilities shared by all action modules.
These are internal (_) and should not be imported outside the actions package.
"""

from __future__ import annotations

import subprocess
import sys
import os
from typing import Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger

logger = get_module_logger(__name__)


def run_command(command: str, timeout: int = 30) -> int:
    """
    Run a shell command and return the exit code.
    stdout/stderr are captured and logged at DEBUG level.

    Args:
        command: Shell command string.
        timeout: Maximum seconds to wait (default 30).

    Returns:
        Return code of the command.
    """
    logger.debug(f"run_command: {command}")
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if result.stdout.strip():
        logger.debug(f"  stdout: {result.stdout.strip()}")
    if result.stderr.strip():
        logger.debug(f"  stderr: {result.stderr.strip()}")
    return result.returncode


def run_command_with_output(command: str, timeout: int = 30) -> Tuple[int, str, str]:
    """
    Run a shell command and return ``(returncode, stdout, stderr)``.

    Args:
        command: Shell command string.
        timeout: Maximum seconds to wait (default 30).

    Returns:
        Tuple of ``(returncode, stdout, stderr)``.
    """
    logger.debug(f"run_command_with_output: {command}")
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def query_tasks_by_prefix(prefix: str, timeout: int = 30) -> list:
    """
    Return a list of schtasks task names whose basename starts with *prefix*.

    Uses ``schtasks /Query /FO CSV /NH`` which lists every scheduled task in
    CSV format without a header row.  The first column is the full task path
    (e.g. ``\\MicrosoftEdgeUpdateTaskMachineCore{GUID}``); the basename is
    the last ``\\``-separated segment.

    Args:
        prefix:  Prefix string to match against the task basename.
        timeout: Seconds before the schtasks query times out (default 30).

    Returns:
        List of task name strings (exactly as schtasks reports them).
        Returns an empty list when the command fails or no tasks match.
    """
    rc, stdout, _ = run_command_with_output(
        "schtasks /Query /FO CSV /NH", timeout=timeout
    )
    if rc != 0:
        return []
    results = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # CSV first field is the task name (quoted)
        task_name = line.split('","')[0].strip('"')
        basename = task_name.lstrip('\\').split('\\')[-1]
        if basename.startswith(prefix):
            results.append(task_name)
    return results


def run_powershell(command: str, timeout: int = 60) -> Tuple[int, str, str]:
    """
    Run a PowerShell command and return ``(returncode, stdout, stderr)``.

    Args:
        command: PowerShell command string (without the ``powershell -Command`` prefix).
        timeout: Maximum seconds to wait (default 60).

    Returns:
        Tuple of ``(returncode, stdout, stderr)``.
    """
    cmd = ["powershell", "-NonInteractive", "-NoProfile", "-Command", command]
    logger.debug(f"run_powershell: {command}")
    result = subprocess.run(
        cmd,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr
