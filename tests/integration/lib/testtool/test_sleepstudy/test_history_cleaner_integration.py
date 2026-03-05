"""
Integration tests for SleepHistoryCleaner.

Two test classes:

1. ``TestHistoryCleanerRealFilesystem``
   Uses ``tmp_path`` with real files on disk — no System32 access needed.
   Validates that the full delete / skip / state-reset flow works against a
   real filesystem (not mocked).

2. ``TestHistoryCleanerSystemPaths``
   Targets the actual ``C:\\Windows\\System32\\SleepStudy`` directories.
   Skipped automatically when:
   - The process is not running as Administrator, OR
   - ``C:\\Windows\\System32\\SleepStudy`` does not exist on this machine.
   Marked ``admin`` so CI can deselect with ``-m "not admin"``.

Run with::

    pytest tests/integration/lib/testtool/test_sleepstudy/test_history_cleaner_integration.py -v

    # Skip the admin / real-system tests:
    pytest ... -m "integration and not admin"
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

import pytest

from lib.testtool.sleepstudy.history_cleaner import (
    SleepHistoryCleaner,
    SLEEP_STUDY_DIR,
    SLEEP_STUDY_SCREENON_DIR,
)
from lib.testtool.sleepstudy.exceptions import SleepStudyClearError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin() -> bool:
    """Return True if the current process has Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _make_files(directory: Path, names: list) -> list:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        p = directory / name
        p.write_text("")
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_sleep_study(tmp_path):
    """
    Two-directory layout mirroring the real SleepStudy structure:
      <tmp>/SleepStudy/
        user-001.etl
        user-002.etl
        ScreenOn/           <- sub-directory (should NOT be deleted)
          screen-001.etl
      <tmp>/SleepStudy/ScreenOn/
        (populated by fixture — same dir object as above)
    """
    root = tmp_path / "SleepStudy"
    screenon = root / "ScreenOn"

    _make_files(root, ["user-001.etl", "user-002.etl"])
    _make_files(screenon, ["screen-001.etl"])

    return {"root": root, "screenon": screenon}


# ===========================================================================
# TestHistoryCleanerRealFilesystem
# ===========================================================================

@pytest.mark.integration
class TestHistoryCleanerRealFilesystem:
    """
    Full end-to-end flow on real (tmp_path) filesystem without mocking.
    Does not require Administrator privileges.
    """

    def test_clears_root_files(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        cleaner = SleepHistoryCleaner(target_dirs=[root])
        count = cleaner.clear()
        assert count == 2

    def test_root_files_gone_after_clear(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        cleaner = SleepHistoryCleaner(target_dirs=[root])
        cleaner.clear()
        remaining = [p for p in root.iterdir() if p.is_file()]
        assert remaining == []

    def test_screenon_subdir_preserved(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        screenon = fake_sleep_study["screenon"]
        cleaner = SleepHistoryCleaner(target_dirs=[root])
        cleaner.clear()
        assert screenon.exists(), "ScreenOn sub-directory must not be deleted"

    def test_screenon_files_not_deleted_by_root_scan(self, fake_sleep_study):
        """Scanning root must not touch files inside ScreenOn."""
        root = fake_sleep_study["root"]
        screenon = fake_sleep_study["screenon"]
        screenon_file = screenon / "screen-001.etl"
        cleaner = SleepHistoryCleaner(target_dirs=[root])
        cleaner.clear()
        assert screenon_file.exists()

    def test_clears_both_dirs_independently(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        screenon = fake_sleep_study["screenon"]
        cleaner = SleepHistoryCleaner(target_dirs=[root, screenon])
        count = cleaner.clear()
        # root: 2 files, screenon: 1 file
        assert count == 3

    def test_both_dirs_empty_after_full_clear(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        screenon = fake_sleep_study["screenon"]
        cleaner = SleepHistoryCleaner(target_dirs=[root, screenon])
        cleaner.clear()
        root_files = [p for p in root.iterdir() if p.is_file()]
        screenon_files = [p for p in screenon.iterdir() if p.is_file()]
        assert root_files == []
        assert screenon_files == []

    def test_directories_still_exist_after_clear(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        screenon = fake_sleep_study["screenon"]
        cleaner = SleepHistoryCleaner(target_dirs=[root, screenon])
        cleaner.clear()
        assert root.exists()
        assert screenon.exists()

    def test_nonexistent_dir_skipped_no_raise(self, tmp_path):
        missing = tmp_path / "NonExistent"
        cleaner = SleepHistoryCleaner(target_dirs=[missing])
        count = cleaner.clear()
        assert count == 0
        assert missing in cleaner.skipped_dirs

    def test_empty_dir_returns_zero(self, tmp_path):
        empty = tmp_path / "EmptyDir"
        empty.mkdir()
        cleaner = SleepHistoryCleaner(target_dirs=[empty])
        count = cleaner.clear()
        assert count == 0
        assert cleaner.errors == []

    def test_state_reset_between_calls(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        cleaner = SleepHistoryCleaner(target_dirs=[root])
        cleaner.clear()                       # first call: deletes 2 files
        _make_files(root, ["new.etl"])        # add one new file
        count = cleaner.clear()               # second call: only new.etl
        assert count == 1
        assert len(cleaner.deleted_files) == 1
        assert cleaner.deleted_files[0].name == "new.etl"

    def test_deleted_files_attribute_accurate(self, fake_sleep_study):
        root = fake_sleep_study["root"]
        cleaner = SleepHistoryCleaner(target_dirs=[root])
        cleaner.clear()
        assert all(not p.exists() for p in cleaner.deleted_files)
        assert len(cleaner.deleted_files) == 2


# ===========================================================================
# TestHistoryCleanerSystemPaths
# ===========================================================================

@pytest.mark.integration
@pytest.mark.admin
class TestHistoryCleanerSystemPaths:
    """
    Tests that target the real ``C:\\Windows\\System32\\SleepStudy`` paths.

    Skipped when:
    - Process is not Administrator, OR
    - ``C:\\Windows\\System32\\SleepStudy`` does not exist on this machine.
    """

    @pytest.fixture(autouse=True)
    def require_admin_and_dir(self):
        if not _is_admin():
            pytest.skip("Administrator privileges required for System32 write access")
        if not SLEEP_STUDY_DIR.exists():
            pytest.skip(f"SleepStudy directory not found: {SLEEP_STUDY_DIR}")

    def test_default_target_dirs_constant(self):
        assert SLEEP_STUDY_DIR == Path(r"C:\Windows\System32\SleepStudy")
        assert SLEEP_STUDY_SCREENON_DIR == Path(r"C:\Windows\System32\SleepStudy\ScreenOn")

    def test_clear_does_not_raise(self):
        """
        clear() must succeed (or gracefully skip missing ScreenOn dir).
        Does not assert a specific count — the directory may already be empty.
        """
        cleaner = SleepHistoryCleaner()
        count = cleaner.clear()
        assert isinstance(count, int)
        assert count >= 0

    def test_sleep_study_dir_still_exists_after_clear(self):
        cleaner = SleepHistoryCleaner()
        cleaner.clear()
        assert SLEEP_STUDY_DIR.exists(), (
            "SleepStudy directory must not be deleted — only its files"
        )

    def test_no_errors_after_clear(self):
        cleaner = SleepHistoryCleaner()
        cleaner.clear()
        assert cleaner.errors == []

    def test_root_dir_contains_no_files_after_clear(self):
        cleaner = SleepHistoryCleaner()
        cleaner.clear()
        remaining_files = [p for p in SLEEP_STUDY_DIR.iterdir() if p.is_file()]
        assert remaining_files == [], (
            f"Expected no files in {SLEEP_STUDY_DIR} after clear, "
            f"found: {remaining_files}"
        )

    def test_screenon_dir_contains_no_files_after_clear(self):
        if not SLEEP_STUDY_SCREENON_DIR.exists():
            pytest.skip(f"ScreenOn directory not found: {SLEEP_STUDY_SCREENON_DIR}")
        cleaner = SleepHistoryCleaner()
        cleaner.clear()
        remaining_files = [p for p in SLEEP_STUDY_SCREENON_DIR.iterdir() if p.is_file()]
        assert remaining_files == [], (
            f"Expected no files in {SLEEP_STUDY_SCREENON_DIR} after clear, "
            f"found: {remaining_files}"
        )
