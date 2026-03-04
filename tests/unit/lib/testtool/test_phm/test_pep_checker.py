"""
Unit tests for lib/testtool/phm/pep_checker.py

All tests use mocks and tmp_path — no real PEPChecker.exe required.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from lib.testtool.phm.pep_checker import (
    PEPChecker,
    PEPCheckerResult,
    EXE_DEFAULT_PATH,
    OUTPUT_FILES,
    DEFAULT_TIMEOUT,
)
from lib.testtool.phm.exceptions import PHMPEPCheckerError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_exe(tmp_path: Path) -> Path:
    """Create a dummy PEPChecker.exe file so _validate_exe passes."""
    exe = tmp_path / "PBC" / "PEPChecker.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.touch()
    return exe


def _seed_output_files(directory: Path) -> None:
    """Create all 4 expected output files in *directory*."""
    for name in OUTPUT_FILES:
        (directory / name).write_text(f"content of {name}")


# ---------------------------------------------------------------------------
# TestPEPCheckerInit
# ---------------------------------------------------------------------------

class TestPEPCheckerInit:
    def test_valid_exe_path(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        checker = PEPChecker(exe_path=exe, log_dir=tmp_path / "log")
        assert checker.exe_path == exe
        assert checker.log_dir == tmp_path / "log"
        assert checker.timeout == DEFAULT_TIMEOUT

    def test_custom_timeout(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        checker = PEPChecker(exe_path=exe, log_dir=tmp_path / "log", timeout=60)
        assert checker.timeout == 60

    def test_string_paths_converted_to_pathlib(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        checker = PEPChecker(exe_path=str(exe), log_dir=str(tmp_path / "log"))
        assert isinstance(checker.exe_path, Path)
        assert isinstance(checker.log_dir, Path)

    def test_missing_exe_raises(self, tmp_path):
        with pytest.raises(PHMPEPCheckerError, match="not found"):
            PEPChecker(
                exe_path=tmp_path / "nonexistent" / "PEPChecker.exe",
                log_dir=tmp_path / "log",
            )

    def test_exit_code_starts_as_none(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        checker = PEPChecker(exe_path=exe, log_dir=tmp_path / "log")
        assert checker._exit_code is None


# ---------------------------------------------------------------------------
# TestRun
# ---------------------------------------------------------------------------

class TestRun:
    def _make_checker(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        return PEPChecker(exe_path=exe, log_dir=tmp_path / "log")

    def test_run_success_returns_0(self, tmp_path):
        checker = self._make_checker(tmp_path)
        mock_result = MagicMock(returncode=0, stderr=b"")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            exit_code = checker.run()

        assert exit_code == 0
        assert checker._exit_code == 0
        # Verify called with exe as first element and correct cwd
        args, kwargs = mock_run.call_args
        assert args[0] == [str(checker.exe_path)]
        assert kwargs["cwd"] == str(checker._working_dir())
        assert kwargs["timeout"] == checker.timeout

    def test_run_non_zero_exit_raises(self, tmp_path):
        checker = self._make_checker(tmp_path)
        mock_result = MagicMock(returncode=1, stderr=b"some error")
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(PHMPEPCheckerError, match="non-zero exit code 1"):
                checker.run()

    def test_run_non_zero_includes_stderr(self, tmp_path):
        checker = self._make_checker(tmp_path)
        mock_result = MagicMock(returncode=2, stderr=b"fatal error")
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(PHMPEPCheckerError, match="fatal error"):
                checker.run()

    def test_run_timeout_raises(self, tmp_path):
        checker = self._make_checker(tmp_path)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            with pytest.raises(PHMPEPCheckerError, match="timed out"):
                checker.run()

    def test_run_file_not_found_raises(self, tmp_path):
        checker = self._make_checker(tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(PHMPEPCheckerError, match="not found at runtime"):
                checker.run()

    def test_run_stores_exit_code(self, tmp_path):
        checker = self._make_checker(tmp_path)
        mock_result = MagicMock(returncode=0, stderr=b"")
        with patch("subprocess.run", return_value=mock_result):
            checker.run()
        assert checker._exit_code == 0


# ---------------------------------------------------------------------------
# TestVerifyOutput
# ---------------------------------------------------------------------------

class TestVerifyOutput:
    def _make_checker(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        return PEPChecker(exe_path=exe, log_dir=tmp_path / "log")

    def test_all_files_present_passes(self, tmp_path):
        checker = self._make_checker(tmp_path)
        working_dir = checker._working_dir()
        _seed_output_files(working_dir)
        checker.verify_output()   # should not raise

    def test_one_missing_file_raises(self, tmp_path):
        checker = self._make_checker(tmp_path)
        working_dir = checker._working_dir()
        _seed_output_files(working_dir)
        (working_dir / "PBC-Errors.txt").unlink()

        with pytest.raises(PHMPEPCheckerError, match="PBC-Errors.txt"):
            checker.verify_output()

    def test_multiple_missing_files_lists_all(self, tmp_path):
        checker = self._make_checker(tmp_path)
        # Don't seed anything — all 4 files missing
        with pytest.raises(PHMPEPCheckerError) as exc_info:
            checker.verify_output()
        msg = str(exc_info.value)
        for name in OUTPUT_FILES:
            assert name in msg

    def test_error_message_includes_working_dir(self, tmp_path):
        checker = self._make_checker(tmp_path)
        with pytest.raises(PHMPEPCheckerError) as exc_info:
            checker.verify_output()
        assert str(checker._working_dir()) in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestCollect
# ---------------------------------------------------------------------------

class TestCollect:
    def _make_checker(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        return PEPChecker(exe_path=exe, log_dir=tmp_path / "log")

    def test_files_moved_to_dest(self, tmp_path):
        checker = self._make_checker(tmp_path)
        working_dir = checker._working_dir()
        _seed_output_files(working_dir)
        dest = tmp_path / "collected"

        result = checker.collect(dest)

        for name in OUTPUT_FILES:
            assert (dest / name).exists(), f"{name} not in dest"
            assert not (working_dir / name).exists(), f"{name} still in src"

    def test_result_paths_are_absolute(self, tmp_path):
        checker = self._make_checker(tmp_path)
        _seed_output_files(checker._working_dir())
        dest = tmp_path / "collected"

        result = checker.collect(dest)

        assert result.report_html.is_absolute()
        assert result.sleep_report_html.is_absolute()
        assert result.debug_log.is_absolute()
        assert result.errors_log.is_absolute()
        assert result.log_dir.is_absolute()

    def test_result_filenames_correct(self, tmp_path):
        checker = self._make_checker(tmp_path)
        _seed_output_files(checker._working_dir())
        dest = tmp_path / "collected"

        result = checker.collect(dest)

        assert result.report_html.name == "PBC-Report.html"
        assert result.sleep_report_html.name == "PBC-sleepstudy-report.html"
        assert result.debug_log.name == "PBC-Debug-Log.txt"
        assert result.errors_log.name == "PBC-Errors.txt"

    def test_existing_dest_is_cleared(self, tmp_path):
        checker = self._make_checker(tmp_path)
        dest = tmp_path / "collected"
        dest.mkdir()
        stale = dest / "stale_file.txt"
        stale.write_text("stale")

        _seed_output_files(checker._working_dir())
        checker.collect(dest)

        assert not stale.exists(), "Stale file should have been removed"

    def test_dest_created_if_missing(self, tmp_path):
        checker = self._make_checker(tmp_path)
        _seed_output_files(checker._working_dir())
        dest = tmp_path / "brand" / "new" / "dir"
        assert not dest.exists()

        checker.collect(dest)

        assert dest.exists()

    def test_missing_src_file_raises(self, tmp_path):
        checker = self._make_checker(tmp_path)
        # Seed only 3 files, omit PBC-Errors.txt
        working_dir = checker._working_dir()
        for name in OUTPUT_FILES[:-1]:
            (working_dir / name).write_text("content")

        with pytest.raises(PHMPEPCheckerError, match="Cannot collect missing file"):
            checker.collect(tmp_path / "dest")

    def test_collect_uses_stored_exit_code(self, tmp_path):
        checker = self._make_checker(tmp_path)
        checker._exit_code = 0
        _seed_output_files(checker._working_dir())

        result = checker.collect(tmp_path / "dest")

        assert result.exit_code == 0

    def test_collect_exit_code_defaults_to_0_when_none(self, tmp_path):
        checker = self._make_checker(tmp_path)
        assert checker._exit_code is None
        _seed_output_files(checker._working_dir())

        result = checker.collect(tmp_path / "dest")

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestRunAndCollect
# ---------------------------------------------------------------------------

class TestRunAndCollect:
    def _make_checker(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        return PEPChecker(exe_path=exe, log_dir=tmp_path / "log")

    def test_happy_path_returns_result(self, tmp_path):
        checker = self._make_checker(tmp_path)
        mock_proc = MagicMock(returncode=0, stderr=b"")

        with patch("subprocess.run", return_value=mock_proc):
            # Seed output files as if the exe created them
            _seed_output_files(checker._working_dir())
            result = checker.run_and_collect()

        assert isinstance(result, PEPCheckerResult)
        assert result.exit_code == 0
        assert result.log_dir == checker.log_dir.resolve()

    def test_call_order_run_verify_collect(self, tmp_path):
        checker = self._make_checker(tmp_path)
        order = []

        real_run = checker.run
        real_verify = checker.verify_output
        real_collect = checker.collect

        def fake_run():
            order.append("run")
            checker._exit_code = 0
            _seed_output_files(checker._working_dir())

        def fake_verify():
            order.append("verify")

        def fake_collect(dest):
            order.append("collect")
            return real_collect(dest)

        checker.run = fake_run
        checker.verify_output = fake_verify
        checker.collect = fake_collect

        # Seed files manually since fake_run seeds them
        checker.run_and_collect()

        assert order == ["run", "verify", "collect"]

    def test_run_failure_propagates(self, tmp_path):
        checker = self._make_checker(tmp_path)
        mock_proc = MagicMock(returncode=1, stderr=b"error")
        with patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(PHMPEPCheckerError, match="non-zero exit code"):
                checker.run_and_collect()

    def test_verify_failure_stops_collect(self, tmp_path):
        """run() succeeds but verify_output() raises — collect() must not run."""
        checker = self._make_checker(tmp_path)

        def fake_run():
            checker._exit_code = 0
            # Deliberately do NOT create output files

        checker.run = fake_run

        with pytest.raises(PHMPEPCheckerError, match="Missing output file"):
            checker.run_and_collect()

        # log_dir must NOT have been created (collect never ran)
        assert not checker.log_dir.exists()


# ---------------------------------------------------------------------------
# TestPEPCheckerResult
# ---------------------------------------------------------------------------

class TestPEPCheckerResult:
    def test_fields_accessible(self, tmp_path):
        result = PEPCheckerResult(
            log_dir=tmp_path,
            report_html=tmp_path / "PBC-Report.html",
            sleep_report_html=tmp_path / "PBC-sleepstudy-report.html",
            debug_log=tmp_path / "PBC-Debug-Log.txt",
            errors_log=tmp_path / "PBC-Errors.txt",
            exit_code=0,
        )
        assert result.exit_code == 0
        assert result.log_dir == tmp_path
        assert result.report_html.name == "PBC-Report.html"

    def test_repr_contains_log_dir(self, tmp_path):
        result = PEPCheckerResult(
            log_dir=tmp_path,
            report_html=tmp_path / "a.html",
            sleep_report_html=tmp_path / "b.html",
            debug_log=tmp_path / "c.txt",
            errors_log=tmp_path / "d.txt",
            exit_code=0,
        )
        assert "PEPCheckerResult" in repr(result)


# ---------------------------------------------------------------------------
# TestDefaultConstants
# ---------------------------------------------------------------------------

class TestDefaultConstants:
    def test_exe_default_path_is_path_object(self):
        assert isinstance(EXE_DEFAULT_PATH, Path)

    def test_exe_default_path_points_to_expected_location(self):
        assert "PowerhouseMountain" in str(EXE_DEFAULT_PATH)
        assert "PEPChecker.exe" in str(EXE_DEFAULT_PATH)

    def test_output_files_has_four_entries(self):
        assert len(OUTPUT_FILES) == 4

    def test_output_files_contains_expected_names(self):
        expected = {
            "PBC-Report.html",
            "PBC-sleepstudy-report.html",
            "PBC-Debug-Log.txt",
            "PBC-Errors.txt",
        }
        assert set(OUTPUT_FILES) == expected

    def test_default_timeout_is_int(self):
        assert isinstance(DEFAULT_TIMEOUT, int)
        assert DEFAULT_TIMEOUT > 0


# ---------------------------------------------------------------------------
# TestWorkingDir
# ---------------------------------------------------------------------------

class TestWorkingDir:
    def test_working_dir_is_exe_parent(self, tmp_path):
        exe = _make_fake_exe(tmp_path)
        checker = PEPChecker(exe_path=exe, log_dir=tmp_path / "log")
        assert checker._working_dir() == exe.parent


# ---------------------------------------------------------------------------
# TestImportsFromPhmPackage
# ---------------------------------------------------------------------------

def test_imports_from_phm_package():
    from lib.testtool.phm import PEPChecker, PEPCheckerResult, PHMPEPCheckerError
    assert PEPChecker is not None
    assert PEPCheckerResult is not None
    assert PHMPEPCheckerError is not None

def test_pep_checker_error_is_phm_error():
    from lib.testtool.phm import PHMPEPCheckerError, PHMError
    assert issubclass(PHMPEPCheckerError, PHMError)
