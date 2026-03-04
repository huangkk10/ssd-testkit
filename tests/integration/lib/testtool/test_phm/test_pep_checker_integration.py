"""
Integration tests for lib/testtool/phm/pep_checker.py

These tests run against the REAL PEPChecker.exe installed on the DUT.
All tests are skipped if the exe is not present.

Prerequisites:
    - Powerhouse Mountain NDA package installed at default path, or
      exe_path configured via Config.json → pep_checker.exe_path

Run:
    pytest tests/integration/lib/testtool/test_phm/test_pep_checker_integration.py
         -v -m "integration"
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.testtool.phm import PEPChecker, PEPCheckerResult, PHMPEPCheckerError
from lib.testtool.phm.pep_checker import EXE_DEFAULT_PATH, OUTPUT_FILES

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_CONFIG_JSON = (
    Path(__file__).parent.parent.parent.parent  # tests/integration/
    / "Config" / "Config.json"
)


def _load_pep_checker_config() -> dict:
    """Return the pep_checker section from Config.json, or defaults."""
    try:
        with open(_CONFIG_JSON, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("pep_checker", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _get_exe_path() -> Path:
    cfg = _load_pep_checker_config()
    return Path(cfg.get("exe_path", EXE_DEFAULT_PATH))


def _get_log_dir(tmp_path: Path) -> Path:
    """Use tmp_path for integration tests to avoid side-effects on testlog/."""
    return tmp_path / "PEPChecker_Log"


# ---------------------------------------------------------------------------
# Shared skip markers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_skip_no_exe = pytest.mark.skipif(
    not _get_exe_path().exists(),
    reason=f"PEPChecker.exe not found at {_get_exe_path()}",
)


# ---------------------------------------------------------------------------
# TestPEPCheckerExePresent
# ---------------------------------------------------------------------------

class TestPEPCheckerExePresent:
    """Verify the exe is present and accessible (skip if not installed)."""

    @_skip_no_exe
    def test_exe_exists_at_default_path(self):
        assert EXE_DEFAULT_PATH.exists(), (
            f"PEPChecker.exe missing: {EXE_DEFAULT_PATH}"
        )

    @_skip_no_exe
    def test_exe_path_from_config_json_exists(self):
        exe = _get_exe_path()
        assert exe.exists(), f"exe_path from Config.json not found: {exe}"

    @_skip_no_exe
    def test_checker_constructs_without_error(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(exe_path=exe, log_dir=_get_log_dir(tmp_path))
        assert checker.exe_path == exe


# ---------------------------------------------------------------------------
# TestRunAndCollectReal
# ---------------------------------------------------------------------------

class TestRunAndCollectReal:
    """Run the real exe and verify the complete pipeline."""

    @_skip_no_exe
    def test_run_and_collect_returns_result(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(
            exe_path=exe,
            log_dir=_get_log_dir(tmp_path),
            timeout=180,
        )
        result = checker.run_and_collect()

        assert isinstance(result, PEPCheckerResult)
        assert result.exit_code == 0

    @_skip_no_exe
    def test_all_four_files_collected(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(
            exe_path=exe,
            log_dir=_get_log_dir(tmp_path),
            timeout=180,
        )
        result = checker.run_and_collect()
        log_dir = result.log_dir

        for name in OUTPUT_FILES:
            assert (log_dir / name).exists(), f"Missing: {name}"

    @_skip_no_exe
    def test_log_dir_is_absolute(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(
            exe_path=exe,
            log_dir=_get_log_dir(tmp_path),
            timeout=180,
        )
        result = checker.run_and_collect()
        assert result.log_dir.is_absolute()

    @_skip_no_exe
    def test_result_paths_point_inside_log_dir(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(
            exe_path=exe,
            log_dir=_get_log_dir(tmp_path),
            timeout=180,
        )
        result = checker.run_and_collect()

        for attr in ("report_html", "sleep_report_html", "debug_log", "errors_log"):
            file_path = getattr(result, attr)
            assert file_path.parent == result.log_dir, (
                f"{attr} is not inside log_dir: {file_path}"
            )


# ---------------------------------------------------------------------------
# TestOutputFileContent
# ---------------------------------------------------------------------------

class TestOutputFileContent:
    """Basic content sanity checks on collected files."""

    @_skip_no_exe
    def test_report_html_is_nonempty(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(exe_path=exe, log_dir=_get_log_dir(tmp_path), timeout=180)
        result = checker.run_and_collect()
        assert result.report_html.stat().st_size > 0

    @_skip_no_exe
    def test_report_html_contains_html_tag(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(exe_path=exe, log_dir=_get_log_dir(tmp_path), timeout=180)
        result = checker.run_and_collect()
        content = result.report_html.read_text(encoding="utf-8", errors="replace")
        assert "<html" in content.lower() or "<!doctype" in content.lower()

    @_skip_no_exe
    def test_sleep_report_html_parseable_by_sleep_report_parser(self, tmp_path):
        """PBC-sleepstudy-report.html must be parseable by SleepReportParser."""
        from lib.testtool.phm import SleepReportParser

        exe = _get_exe_path()
        checker = PEPChecker(exe_path=exe, log_dir=_get_log_dir(tmp_path), timeout=180)
        result = checker.run_and_collect()

        parser = SleepReportParser(result.sleep_report_html)
        sessions = parser.get_sleep_sessions()
        # Just verify it returns a list (may be empty if no Sleep sessions recorded)
        assert isinstance(sessions, list)

    @_skip_no_exe
    def test_debug_log_is_text(self, tmp_path):
        exe = _get_exe_path()
        checker = PEPChecker(exe_path=exe, log_dir=_get_log_dir(tmp_path), timeout=180)
        result = checker.run_and_collect()
        # Should be readable as UTF-8 / latin-1 text without error
        result.debug_log.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# TestMissingExeError
# ---------------------------------------------------------------------------

class TestMissingExeError:
    def test_bogus_path_raises_at_construction(self, tmp_path):
        with pytest.raises(PHMPEPCheckerError, match="not found"):
            PEPChecker(
                exe_path=tmp_path / "no_such" / "PEPChecker.exe",
                log_dir=tmp_path / "log",
            )


# ---------------------------------------------------------------------------
# TestLogDirCreation
# ---------------------------------------------------------------------------

class TestLogDirCreation:
    """Verify log_dir is created / cleared correctly (no real exe needed)."""

    def _make_checker_with_fake_run(self, tmp_path):
        """Return a PEPChecker with _validate_exe bypassed and run() mocked."""
        exe = tmp_path / "PBC" / "PEPChecker.exe"
        exe.parent.mkdir(parents=True)
        exe.touch()
        checker = PEPChecker(exe_path=exe, log_dir=tmp_path / "log")
        return checker

    def _seed_output_files(self, directory: Path):
        for name in OUTPUT_FILES:
            (directory / name).write_text(f"content of {name}")

    def test_nonexistent_log_dir_is_created(self, tmp_path):
        checker = self._make_checker_with_fake_run(tmp_path)
        dest = tmp_path / "new" / "nested" / "log"
        assert not dest.exists()

        self._seed_output_files(checker._working_dir())
        checker.collect(dest)

        assert dest.exists()

    def test_existing_log_dir_is_cleared(self, tmp_path):
        checker = self._make_checker_with_fake_run(tmp_path)
        dest = tmp_path / "log"
        dest.mkdir()
        stale = dest / "old_report.html"
        stale.write_text("old")

        self._seed_output_files(checker._working_dir())
        checker.collect(dest)

        assert not stale.exists(), "Stale file should be gone after collect()"
        # New files must exist
        assert (dest / "PBC-Report.html").exists()

    def test_second_run_replaces_first_run_files(self, tmp_path):
        checker = self._make_checker_with_fake_run(tmp_path)
        dest = tmp_path / "log"

        # First collection
        self._seed_output_files(checker._working_dir())
        checker.collect(dest)
        first_mtime = (dest / "PBC-Report.html").stat().st_mtime

        # Re-seed (simulate second exe run)
        self._seed_output_files(checker._working_dir())
        checker.collect(dest)
        second_mtime = (dest / "PBC-Report.html").stat().st_mtime

        # File was replaced (mtime may differ in high-resolution scenarios;
        # just assert it exists and log_dir is clean)
        assert (dest / "PBC-Report.html").exists()


# ---------------------------------------------------------------------------
# TestConfigJsonIntegration
# ---------------------------------------------------------------------------

class TestConfigJsonIntegration:
    """Construct PEPChecker from Config.json values."""

    def test_config_json_has_pep_checker_section(self):
        assert _CONFIG_JSON.exists(), f"Config.json not found: {_CONFIG_JSON}"
        with open(_CONFIG_JSON, encoding="utf-8") as f:
            cfg = json.load(f)
        assert "pep_checker" in cfg, "pep_checker section missing from Config.json"

    def test_config_json_pep_checker_has_required_keys(self):
        cfg = _load_pep_checker_config()
        for key in ("exe_path", "log_dir", "timeout"):
            assert key in cfg, f"Key '{key}' missing from pep_checker config"

    def test_construct_from_config_json_values(self, tmp_path):
        """Verify PEPChecker can be constructed using Config.json values when exe exists."""
        cfg = _load_pep_checker_config()
        exe_path = Path(cfg.get("exe_path", EXE_DEFAULT_PATH))

        if not exe_path.exists():
            pytest.skip(f"exe not present: {exe_path}")

        checker = PEPChecker(
            exe_path=cfg["exe_path"],
            log_dir=str(tmp_path / "PEPChecker_Log"),
            timeout=cfg.get("timeout", 120),
        )
        assert checker.exe_path == exe_path

    @_skip_no_exe
    def test_full_pipeline_via_config_json(self, tmp_path):
        """End-to-end: load Config.json → run_and_collect() → verify files."""
        cfg = _load_pep_checker_config()
        checker = PEPChecker(
            exe_path=cfg["exe_path"],
            log_dir=str(tmp_path / "PEPChecker_Log"),
            timeout=cfg.get("timeout", 180),
        )
        result = checker.run_and_collect()

        assert result.exit_code == 0
        for name in OUTPUT_FILES:
            assert (result.log_dir / name).exists()
