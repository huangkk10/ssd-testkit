"""
SleepStudy History Cleaner

Deletes accumulated Sleep Study record files from the Windows system
directories before starting a new test run, ensuring the next
``powercfg /sleepstudy`` report contains only sessions from the current
test cycle.

Target directories (files only — directories are preserved):
- ``C:\\Windows\\System32\\SleepStudy\\``
- ``C:\\Windows\\System32\\SleepStudy\\ScreenOn\\``

Requires Administrator privileges.

Usage::

    from lib.testtool.sleepstudy import SleepHistoryCleaner

    cleaner = SleepHistoryCleaner()
    deleted = cleaner.clear()          # raises SleepStudyClearError on failure
    print(f"Deleted {deleted} files")
    print(f"Skipped (not found): {cleaner.skipped_dirs}")
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from lib.logger import get_module_logger
from .exceptions import SleepStudyClearError

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# Default system paths
# ---------------------------------------------------------------------------

SLEEP_STUDY_DIR = Path(r"C:\Windows\System32\SleepStudy")
SLEEP_STUDY_SCREENON_DIR = Path(r"C:\Windows\System32\SleepStudy\ScreenOn")


class SleepHistoryCleaner:
    """
    Deletes all files inside the Sleep Study system directories.

    Only **direct child files** of each target directory are deleted;
    sub-directories themselves are never removed.  Because
    ``SleepStudy\\ScreenOn`` is listed as a separate explicit target, its
    files are cleaned in a dedicated pass — the parent scan of
    ``SleepStudy\\`` skips it automatically via :meth:`Path.is_file`.

    Args:
        target_dirs:
            Override the list of directories to clear.  Each element may be
            a :class:`str` or :class:`~pathlib.Path`.  Defaults to
            :data:`DEFAULT_TARGET_DIRS` (the two system paths above).
            Pass a custom list when unit-testing to avoid touching the real
            file system.

    Attributes:
        deleted_files  (list[Path]): Files successfully deleted in the last
            :meth:`clear` call.
        skipped_dirs   (list[Path]): Target directories that did not exist
            and were silently skipped.
        errors         (list[tuple[Path, Exception]]): ``(file, exception)``
            pairs collected when *raise_on_error* is ``False``.

    Example::

        cleaner = SleepHistoryCleaner()
        count = cleaner.clear()
        print(f"Cleared {count} files; skipped dirs: {cleaner.skipped_dirs}")
    """

    DEFAULT_TARGET_DIRS: List[Path] = [
        SLEEP_STUDY_DIR,
        SLEEP_STUDY_SCREENON_DIR,
    ]

    def __init__(
        self,
        target_dirs: Optional[List] = None,
    ) -> None:
        self._target_dirs: List[Path] = [
            Path(p) for p in (target_dirs if target_dirs is not None else self.DEFAULT_TARGET_DIRS)
        ]
        self.deleted_files: List[Path] = []
        self.skipped_dirs: List[Path] = []
        self.errors: List[Tuple[Path, Exception]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear(self, raise_on_error: bool = True) -> int:
        """
        Delete all direct-child files in each target directory.

        Resets :attr:`deleted_files`, :attr:`skipped_dirs`, and
        :attr:`errors` at the start of each invocation so that repeated
        calls return fresh state.

        Args:
            raise_on_error:
                ``True`` (default) — stop and raise :class:`~.exceptions.SleepStudyClearError`
                on the first deletion failure.
                ``False`` — collect failures in :attr:`errors` and continue.

        Returns:
            Number of files successfully deleted.

        Raises:
            :class:`~.exceptions.SleepStudyClearError`:
                A file could not be deleted (e.g. ``PermissionError`` when
                not running as Administrator, or ``OSError`` for a locked
                file).  Only raised when *raise_on_error* is ``True``.
        """
        # Reset state so repeated calls are idempotent.
        self.deleted_files = []
        self.skipped_dirs = []
        self.errors = []

        for directory in self._target_dirs:
            self._clear_directory(directory, raise_on_error)

        logger.info(
            "SleepHistoryCleaner: cleared %d file(s); skipped %d dir(s); "
            "%d error(s)",
            len(self.deleted_files),
            len(self.skipped_dirs),
            len(self.errors),
        )
        return len(self.deleted_files)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clear_directory(self, directory: Path, raise_on_error: bool) -> None:
        """Remove all files directly inside *directory*."""
        if not directory.exists():
            self.skipped_dirs.append(directory)
            logger.warning(
                "SleepHistoryCleaner: directory not found, skipping — %s",
                directory,
            )
            return

        for item in directory.iterdir():
            if not item.is_file():
                # Sub-directories (e.g. ScreenOn under SleepStudy) are
                # handled as separate target_dirs entries — skip here.
                logger.debug("Skipping non-file entry: %s", item)
                continue
            self._delete_file(item, raise_on_error)

    def _delete_file(self, file_path: Path, raise_on_error: bool) -> None:
        """Attempt to unlink *file_path*, recording the outcome."""
        try:
            file_path.unlink()
            self.deleted_files.append(file_path)
            logger.debug("Deleted: %s", file_path)
        except PermissionError as exc:
            err = SleepStudyClearError(
                f"Permission denied deleting {file_path}. "
                f"Ensure the process is running as Administrator. "
                f"Original error: {exc}"
            )
            self.errors.append((file_path, err))
            logger.error(str(err))
            if raise_on_error:
                raise err from exc
        except OSError as exc:
            err = SleepStudyClearError(
                f"Failed to delete {file_path}: {exc}"
            )
            self.errors.append((file_path, err))
            logger.error(str(err))
            if raise_on_error:
                raise err from exc
