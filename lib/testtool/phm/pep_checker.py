"""
PEPChecker (Powerhouse Mountain NDA Collector) Wrapper

Runs PEPChecker.exe, verifies output files, and collects them into a log folder.

Typical usage::

    from lib.testtool.phm import PEPChecker, SleepReportParser

    checker = PEPChecker(
        exe_path=r"C:\\Program Files\\PowerhouseMountain\\NDA\\collectors\\windows\\PBC\\PEPChecker.exe",
        log_dir=r".\\testlog\\PEPChecker_Log",
    )
    result = checker.run_and_collect()

    # Optionally parse the collected sleep report
    parser = SleepReportParser(result.sleep_report_html)
    sessions = parser.get_sleep_sessions()
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

from .exceptions import PHMPEPCheckerError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

#: Default path to PEPChecker.exe (Powerhouse Mountain NDA installation).
EXE_DEFAULT_PATH: Path = Path(
    r"C:\Program Files\PowerhouseMountain\NDA\collectors\windows\PBC\PEPChecker.exe"
)

#: Names of all files that PEPChecker.exe is expected to produce.
OUTPUT_FILES: tuple = (
    "PBC-Report.html",
    "PBC-sleepstudy-report.html",
    "PBC-Debug-Log.txt",
    "PBC-Errors.txt",
)

#: Default execution timeout in seconds.
DEFAULT_TIMEOUT: int = 120


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PEPCheckerResult:
    """
    Container for PEPChecker output file paths after collection.

    All path attributes are absolute :class:`pathlib.Path` objects pointing
    to files inside *log_dir*.

    Attributes:
        log_dir:           Folder where files were collected.
        report_html:       Path to ``PBC-Report.html``.
        sleep_report_html: Path to ``PBC-sleepstudy-report.html``.
        debug_log:         Path to ``PBC-Debug-Log.txt``.
        errors_log:        Path to ``PBC-Errors.txt``.
        exit_code:         Exit code returned by PEPChecker.exe.

    Example:
        >>> result = checker.run_and_collect()
        >>> print(result.sleep_report_html)
        C:\\testlog\\PEPChecker_Log\\PBC-sleepstudy-report.html
    """

    log_dir:             Path
    report_html:         Path
    sleep_report_html:   Path
    debug_log:           Path
    errors_log:          Path
    exit_code:           int


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class PEPChecker:
    """
    Wrapper for PEPChecker.exe (Powerhouse Mountain NDA collector).

    Runs the tool, validates all expected output files are present, and
    collects them into a designated log folder.

    Args:
        exe_path (str | Path):
            Full path to ``PEPChecker.exe``.
            Defaults to the standard NDA installation path.
        log_dir (str | Path):
            Destination folder for collected output files.
            Cleared before collection if it already exists.
        timeout (int):
            Maximum seconds to wait for the exe to finish.  Default ``120``.

    Raises:
        PHMPEPCheckerError:
            - ``exe_path`` does not exist at construction time.
            - ``PEPChecker.exe`` returns a non-zero exit code.
            - ``PEPChecker.exe`` exceeds *timeout*.
            - One or more expected output files are missing after execution.

    Example::

        checker = PEPChecker(
            exe_path=r"C:\\Program Files\\PowerhouseMountain\\NDA\\collectors\\windows\\PBC\\PEPChecker.exe",
            log_dir=r".\\testlog\\PEPChecker_Log",
        )
        result = checker.run_and_collect()
        print(result.log_dir)
        print(result.sleep_report_html)
    """

    def __init__(
        self,
        exe_path: Union[str, Path] = EXE_DEFAULT_PATH,
        log_dir: Union[str, Path] = "./testlog/PEPChecker_Log",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.exe_path: Path = Path(exe_path)
        self.log_dir: Path = Path(log_dir)
        self.timeout: int = timeout
        self._exit_code: Optional[int] = None
        self._validate_exe()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> int:
        """
        Launch ``PEPChecker.exe`` in its own directory and wait for completion.

        PEPChecker generates output files relative to its own directory, so
        the working directory is set to ``exe_path.parent``.

        Returns:
            int: Exit code from the process (``0`` on success).

        Raises:
            PHMPEPCheckerError:
                If the exe is not found at runtime, times out, or exits
                with a non-zero code.

        Example:
            >>> exit_code = checker.run()
            >>> assert exit_code == 0
        """
        working_dir = self._working_dir()
        logger.info(f"Launching PEPChecker: {self.exe_path}")

        try:
            proc = subprocess.run(
                [str(self.exe_path)],
                cwd=str(working_dir),
                timeout=self.timeout,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            raise PHMPEPCheckerError(
                f"PEPChecker.exe timed out after {self.timeout} seconds"
            )
        except FileNotFoundError:
            raise PHMPEPCheckerError(
                f"PEPChecker.exe not found at runtime: {self.exe_path}"
            )

        self._exit_code = proc.returncode
        logger.info(f"PEPChecker.exe exited with code {self._exit_code}")

        if self._exit_code != 0:
            stderr_text = proc.stderr.decode(errors="replace").strip()
            raise PHMPEPCheckerError(
                f"PEPChecker.exe returned non-zero exit code {self._exit_code}"
                + (f": {stderr_text}" if stderr_text else "")
            )

        return self._exit_code

    def verify_output(self) -> None:
        """
        Check that all expected output files exist in the exe's working directory.

        Raises:
            PHMPEPCheckerError:
                Lists all missing filenames in the error message.

        Example:
            >>> checker.verify_output()   # raises if any file is missing
        """
        working_dir = self._working_dir()
        missing = [
            name for name in OUTPUT_FILES
            if not (working_dir / name).exists()
        ]
        if missing:
            raise PHMPEPCheckerError(
                f"Missing output file(s) in {working_dir}: {', '.join(missing)}"
            )
        logger.info(
            f"All {len(OUTPUT_FILES)} output files verified in {working_dir}"
        )

    def collect(self, dest_dir: Union[str, Path]) -> PEPCheckerResult:
        """
        Clear *dest_dir*, then move all output files from the exe's working
        directory into it.

        Args:
            dest_dir (str | Path):
                Target folder.  Created if it does not exist; fully cleared
                first if it already exists.

        Returns:
            PEPCheckerResult: Dataclass with absolute paths to all collected files.

        Raises:
            PHMPEPCheckerError: If a source file is missing during the move.

        Example:
            >>> result = checker.collect("./testlog/PEPChecker_Log")
            >>> print(result.report_html)
        """
        dest = Path(dest_dir).resolve()
        working_dir = self._working_dir()

        # Clear existing contents so stale files do not linger.
        if dest.exists():
            shutil.rmtree(dest)
            logger.info(f"Cleared existing log_dir: {dest}")

        dest.mkdir(parents=True, exist_ok=True)

        collected: Dict[str, Path] = {}
        for name in OUTPUT_FILES:
            src = working_dir / name
            if not src.exists():
                raise PHMPEPCheckerError(
                    f"Cannot collect missing file: {src}"
                )
            shutil.move(str(src), str(dest / name))
            collected[name] = dest / name
            logger.info(f"Collected: {src} -> {dest / name}")

        return PEPCheckerResult(
            log_dir=dest,
            report_html=collected["PBC-Report.html"],
            sleep_report_html=collected["PBC-sleepstudy-report.html"],
            debug_log=collected["PBC-Debug-Log.txt"],
            errors_log=collected["PBC-Errors.txt"],
            exit_code=self._exit_code if self._exit_code is not None else 0,
        )

    def run_and_collect(self) -> PEPCheckerResult:
        """
        Convenience method: ``run()`` → ``verify_output()`` → ``collect(log_dir)``.

        Returns:
            PEPCheckerResult: Dataclass with absolute paths to all collected files.

        Raises:
            PHMPEPCheckerError: On any failure in the pipeline.

        Example::

            result = checker.run_and_collect()
            print(result.sleep_report_html)
        """
        self.run()
        self.verify_output()
        return self.collect(self.log_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_exe(self) -> None:
        """Raise :exc:`PHMPEPCheckerError` if *exe_path* does not exist."""
        if not self.exe_path.exists():
            raise PHMPEPCheckerError(
                f"PEPChecker.exe not found at: {self.exe_path}"
            )

    def _working_dir(self) -> Path:
        """Return the directory containing the exe (output files land here)."""
        return self.exe_path.parent
