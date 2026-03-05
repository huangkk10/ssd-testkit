"""
Unit tests for lib.testtool.sleepstudy.history_cleaner

All tests use pytest's `tmp_path` fixture — no System32 paths are touched.
File-system operations are exercised on real temporary files/directories;
only PermissionError / locked-file scenarios use mocks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

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

def _make_files(directory: Path, names: list[str]) -> list[Path]:
    """Create empty files in *directory*, return their paths."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        p = directory / name
        p.write_text("")
        paths.append(p)
    return paths


# ===========================================================================
# TestSleepHistoryCleanerInit
# ===========================================================================

class TestSleepHistoryCleanerInit:
    def test_default_target_dirs(self):
        cleaner = SleepHistoryCleaner()
        assert cleaner._target_dirs == [SLEEP_STUDY_DIR, SLEEP_STUDY_SCREENON_DIR]

    def test_custom_target_dirs_paths(self, tmp_path):
        d1 = tmp_path / "A"
        d2 = tmp_path / "B"
        cleaner = SleepHistoryCleaner(target_dirs=[d1, d2])
        assert cleaner._target_dirs == [d1, d2]

    def test_custom_target_dirs_strings(self, tmp_path):
        d1 = tmp_path / "A"
        cleaner = SleepHistoryCleaner(target_dirs=[str(d1)])
        assert cleaner._target_dirs == [d1]

    def test_initial_state_empty(self):
        cleaner = SleepHistoryCleaner()
        assert cleaner.deleted_files == []
        assert cleaner.skipped_dirs == []
        assert cleaner.errors == []


# ===========================================================================
# TestClearNormalFlow
# ===========================================================================

class TestClearNormalFlow:
    def test_deletes_files_returns_count(self, tmp_path):
        d = tmp_path / "SleepStudy"
        files = _make_files(d, ["a.etl", "b.etl", "c.xml"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        count = cleaner.clear()
        assert count == 3

    def test_deleted_files_populated(self, tmp_path):
        d = tmp_path / "SleepStudy"
        files = _make_files(d, ["a.etl", "b.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        cleaner.clear()
        assert set(cleaner.deleted_files) == set(files)

    def test_files_actually_removed(self, tmp_path):
        d = tmp_path / "SleepStudy"
        files = _make_files(d, ["x.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        cleaner.clear()
        assert not files[0].exists()

    def test_subdirectory_not_deleted(self, tmp_path):
        d = tmp_path / "SleepStudy"
        subdir = d / "ScreenOn"
        subdir.mkdir(parents=True)
        _make_files(d, ["a.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        cleaner.clear()
        assert subdir.exists(), "Sub-directory must not be removed"

    def test_subdirectory_not_counted(self, tmp_path):
        d = tmp_path / "SleepStudy"
        subdir = d / "ScreenOn"
        subdir.mkdir(parents=True)
        _make_files(d, ["a.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        count = cleaner.clear()
        # Only a.etl is a file — ScreenOn subdir must not be counted
        assert count == 1

    def test_no_errors_on_success(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["a.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        cleaner.clear()
        assert cleaner.errors == []


# ===========================================================================
# TestClearMultipleDirs
# ===========================================================================

class TestClearMultipleDirs:
    def test_clears_both_dirs(self, tmp_path):
        d1 = tmp_path / "SleepStudy"
        d2 = tmp_path / "ScreenOn"
        _make_files(d1, ["a.etl", "b.etl"])
        _make_files(d2, ["c.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d1, d2])
        count = cleaner.clear()
        assert count == 3

    def test_deleted_files_from_both_dirs(self, tmp_path):
        d1 = tmp_path / "SleepStudy"
        d2 = tmp_path / "ScreenOn"
        files1 = _make_files(d1, ["a.etl"])
        files2 = _make_files(d2, ["b.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d1, d2])
        cleaner.clear()
        assert set(cleaner.deleted_files) == {files1[0], files2[0]}


# ===========================================================================
# TestClearDirNotExist
# ===========================================================================

class TestClearDirNotExist:
    def test_nonexistent_dir_skipped(self, tmp_path):
        missing = tmp_path / "DoesNotExist"
        cleaner = SleepHistoryCleaner(target_dirs=[missing])
        count = cleaner.clear()
        assert count == 0
        assert missing in cleaner.skipped_dirs

    def test_nonexistent_dir_does_not_raise(self, tmp_path):
        missing = tmp_path / "DoesNotExist"
        cleaner = SleepHistoryCleaner(target_dirs=[missing])
        # Must not raise
        cleaner.clear()

    def test_continues_after_skipped_dir(self, tmp_path):
        missing = tmp_path / "DoesNotExist"
        present = tmp_path / "Present"
        _make_files(present, ["f.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[missing, present])
        count = cleaner.clear()
        assert count == 1
        assert missing in cleaner.skipped_dirs


# ===========================================================================
# TestClearPermissionErrorRaiseOnError
# ===========================================================================

class TestClearPermissionErrorRaiseOnError:
    def test_raises_sleepstudy_clear_error(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["locked.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        with patch.object(Path, "unlink", side_effect=PermissionError("access denied")):
            with pytest.raises(SleepStudyClearError) as exc_info:
                cleaner.clear(raise_on_error=True)

        assert "Administrator" in str(exc_info.value)

    def test_error_cause_is_permission_error(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["locked.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        with patch.object(Path, "unlink", side_effect=PermissionError("access denied")):
            with pytest.raises(SleepStudyClearError) as exc_info:
                cleaner.clear()

        assert isinstance(exc_info.value.__cause__, PermissionError)

    def test_raises_on_first_failure(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["f1.etl", "f2.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        call_count = 0
        original_unlink = Path.unlink

        def unlink_once_then_fail(self, missing_ok=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                original_unlink(self, missing_ok=missing_ok)
            else:
                raise PermissionError("no access")

        with patch.object(Path, "unlink", unlink_once_then_fail):
            with pytest.raises(SleepStudyClearError):
                cleaner.clear(raise_on_error=True)

        # Stopped after first error, so only 1 file in deleted_files
        assert len(cleaner.deleted_files) == 1


# ===========================================================================
# TestClearPermissionErrorNoRaise
# ===========================================================================

class TestClearPermissionErrorNoRaise:
    def test_no_raise_collects_error(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["locked.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            count = cleaner.clear(raise_on_error=False)

        assert count == 0
        assert len(cleaner.errors) == 1
        file_path, exc = cleaner.errors[0]
        assert isinstance(exc, SleepStudyClearError)

    def test_no_raise_continues_after_error(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["f1.etl", "f2.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        call_count = 0
        original_unlink = Path.unlink

        def fail_first_then_succeed(self, missing_ok=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PermissionError("denied")
            original_unlink(self, missing_ok=missing_ok)

        with patch.object(Path, "unlink", fail_first_then_succeed):
            count = cleaner.clear(raise_on_error=False)

        # One error + one success
        assert len(cleaner.errors) == 1
        assert count == 1

    def test_no_raise_returns_zero_all_fail(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["a.etl", "b.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            count = cleaner.clear(raise_on_error=False)

        assert count == 0
        assert len(cleaner.errors) == 2


# ===========================================================================
# TestClearOSError
# ===========================================================================

class TestClearOSError:
    def test_oserror_raises_clear_error(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["locked.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        with patch.object(Path, "unlink", side_effect=OSError("file in use")):
            with pytest.raises(SleepStudyClearError):
                cleaner.clear()

    def test_oserror_cause_chained(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["locked.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        original_exc = OSError("file in use")

        with patch.object(Path, "unlink", side_effect=original_exc):
            with pytest.raises(SleepStudyClearError) as exc_info:
                cleaner.clear()

        assert isinstance(exc_info.value.__cause__, OSError)

    def test_oserror_no_raise_collected(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["locked.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        with patch.object(Path, "unlink", side_effect=OSError("file in use")):
            cleaner.clear(raise_on_error=False)

        assert len(cleaner.errors) == 1
        _, exc = cleaner.errors[0]
        assert isinstance(exc, SleepStudyClearError)


# ===========================================================================
# TestClearStateReset
# ===========================================================================

class TestClearStateReset:
    def test_second_call_resets_deleted_files(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["a.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        cleaner.clear()          # first call: deletes a.etl
        _make_files(d, ["b.etl"])
        cleaner.clear()          # second call: deletes b.etl; a.etl already gone

        assert len(cleaner.deleted_files) == 1
        assert cleaner.deleted_files[0].name == "b.etl"

    def test_second_call_resets_errors(self, tmp_path):
        d = tmp_path / "SleepStudy"
        _make_files(d, ["a.etl"])
        cleaner = SleepHistoryCleaner(target_dirs=[d])

        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            cleaner.clear(raise_on_error=False)

        assert len(cleaner.errors) == 1

        # Second call: no error
        _make_files(d, ["a.etl"])  # recreate
        cleaner.clear()
        assert cleaner.errors == []

    def test_second_call_resets_skipped_dirs(self, tmp_path):
        missing = tmp_path / "Missing"
        cleaner = SleepHistoryCleaner(target_dirs=[missing])
        cleaner.clear()
        first_skipped = list(cleaner.skipped_dirs)

        cleaner.clear()          # second call
        assert cleaner.skipped_dirs == first_skipped  # same result, not accumulated


# ===========================================================================
# TestEmptyDirectory
# ===========================================================================

class TestEmptyDirectory:
    def test_empty_dir_returns_zero(self, tmp_path):
        d = tmp_path / "SleepStudy"
        d.mkdir()
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        count = cleaner.clear()
        assert count == 0

    def test_empty_dir_no_errors(self, tmp_path):
        d = tmp_path / "SleepStudy"
        d.mkdir()
        cleaner = SleepHistoryCleaner(target_dirs=[d])
        cleaner.clear()
        assert cleaner.errors == []
        assert cleaner.skipped_dirs == []
        assert cleaner.deleted_files == []
