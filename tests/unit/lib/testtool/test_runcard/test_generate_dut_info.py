"""
Unit tests for Runcard.generate_dut_info() — path resolution logic.

All tests mock subprocess.run and os.path.exists so no real SmiCli2.exe
or filesystem state is required.

Coverage targets (the change introduced in this session):
  1. Explicit smicli_path argument wins (priority 1)
  2. SMICLI_PATH env var used when no explicit arg (priority 2)
  3. SSD_TESTKIT_ROOT fallback path (priority 3)
  4. Legacy default when nothing is set (priority 4)
  5. Path that is already absolute is NOT re-joined with work_dir
  6. Relative path IS joined with work_dir
  7. Returns False (and sets error_message) when resolved exe is missing
  8. Returns True on subprocess exit-code 0 with valid output file
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from lib.testtool.RunCard import Runcard


# ── helpers ────────────────────────────────────────────────────────────────

def _make_runcard(tmp_path) -> Runcard:
    """Return a Runcard whose test path sits in pytest's tmp_path."""
    return Runcard(test_path=str(tmp_path))


def _mock_subprocess_ok(output_content: str = "[info]\nos=Windows 11\n[disk_0]\nid=0\n"):
    """
    Return a context-manager patch for subprocess.run that:
      - exits with code 0
      - writes *output_content* to the output file (simulated via exists+read).
    """
    proc = MagicMock()
    proc.returncode = 0
    proc.stderr = ""
    return patch("subprocess.run", return_value=proc)


# ══════════════════════════════════════════════════════════════════════════
# Priority resolution tests
# ══════════════════════════════════════════════════════════════════════════

class TestResolveSmicliPath:
    """Verify the four-level path resolution order."""

    def _run_resolve_only(self, runcard, env, explicit_arg=None):
        """
        Call generate_dut_info in an environment where the exe is *always*
        reported as missing, so we can capture what path was resolved.
        The method returns False because the file doesn't exist — that's OK,
        we only care about error_message which contains the resolved path.
        """
        with patch.dict(os.environ, env, clear=True), \
             patch("os.path.exists", return_value=False), \
             patch("os.getcwd", return_value="C:\\fake_cwd"):
            kwargs = {}
            if explicit_arg is not None:
                kwargs["smicli_path"] = explicit_arg
            runcard.generate_dut_info(output_file="C:\\tmp\\out.ini", **kwargs)
        return runcard.error_message  # contains the resolved path

    def test_priority1_explicit_arg(self, tmp_path):
        rc = _make_runcard(tmp_path)
        msg = self._run_resolve_only(
            rc,
            env={"SMICLI_PATH": "C:\\env_path\\SmiCli2.exe",
                 "SSD_TESTKIT_ROOT": "C:\\root"},
            explicit_arg="C:\\explicit\\SmiCli2.exe",
        )
        assert "C:\\explicit\\SmiCli2.exe" in msg

    def test_priority2_smicli_path_env(self, tmp_path):
        rc = _make_runcard(tmp_path)
        msg = self._run_resolve_only(
            rc,
            env={"SMICLI_PATH": "C:\\env_path\\SmiCli2.exe",
                 "SSD_TESTKIT_ROOT": "C:\\root"},
        )
        assert "C:\\env_path\\SmiCli2.exe" in msg

    def test_priority3_ssd_testkit_root(self, tmp_path):
        rc = _make_runcard(tmp_path)
        msg = self._run_resolve_only(
            rc,
            env={"SSD_TESTKIT_ROOT": "C:\\root"},
        )
        assert os.path.join("C:\\root", "bin", "installers", "SmiCli", "SmiCli2.exe") in msg

    def test_priority4_legacy_default(self, tmp_path):
        rc = _make_runcard(tmp_path)
        msg = self._run_resolve_only(rc, env={})
        # legacy ".\\bin\\SmiCli\\SmiCli2.exe" is joined with work_dir;
        # os.path.join preserves the leading .\ so check for the sub-path only
        assert "bin\\SmiCli\\SmiCli2.exe" in msg
        assert "C:\\fake_cwd" in msg

    def test_explicit_arg_overrides_env_var(self, tmp_path):
        """Priority 1 beats priority 2."""
        rc = _make_runcard(tmp_path)
        msg = self._run_resolve_only(
            rc,
            env={"SMICLI_PATH": "C:\\should_not_use\\SmiCli2.exe"},
            explicit_arg="C:\\override\\SmiCli2.exe",
        )
        assert "C:\\override\\SmiCli2.exe" in msg
        assert "should_not_use" not in msg

    def test_env_var_overrides_ssd_testkit_root(self, tmp_path):
        """Priority 2 beats priority 3."""
        rc = _make_runcard(tmp_path)
        msg = self._run_resolve_only(
            rc,
            env={"SMICLI_PATH": "C:\\env_win\\SmiCli2.exe",
                 "SSD_TESTKIT_ROOT": "C:\\root"},
        )
        assert "C:\\env_win\\SmiCli2.exe" in msg
        assert "C:\\root" not in msg


# ══════════════════════════════════════════════════════════════════════════
# Absolute vs relative path handling
# ══════════════════════════════════════════════════════════════════════════

class TestPathAbsoluteness:

    def test_absolute_path_not_re_joined(self, tmp_path):
        """An already-absolute path must not be prefixed with work_dir."""
        rc = _make_runcard(tmp_path)
        with patch.dict(os.environ, {}, clear=True), \
             patch("os.path.exists", return_value=False), \
             patch("os.getcwd", return_value="C:\\cwd"):
            rc.generate_dut_info(
                smicli_path="C:\\absolute\\SmiCli2.exe",
                output_file="C:\\tmp\\out.ini",
            )
        assert "C:\\absolute\\SmiCli2.exe" in rc.error_message
        assert "C:\\cwd" not in rc.error_message

    def test_relative_path_joined_with_workdir(self, tmp_path):
        """A relative path must be resolved against work_dir."""
        rc = _make_runcard(tmp_path)
        with patch.dict(os.environ, {}, clear=True), \
             patch("os.path.exists", return_value=False), \
             patch("os.getcwd", return_value="C:\\cwd"):
            rc.generate_dut_info(
                smicli_path="relative\\SmiCli2.exe",
                output_file="C:\\tmp\\out.ini",
                work_dir="C:\\workdir",
            )
        assert os.path.join("C:\\workdir", "relative\\SmiCli2.exe") in rc.error_message


# ══════════════════════════════════════════════════════════════════════════
# Return value: exe missing
# ══════════════════════════════════════════════════════════════════════════

class TestReturnValueWhenExeMissing:

    def test_returns_false_when_exe_not_found(self, tmp_path):
        rc = _make_runcard(tmp_path)
        with patch.dict(os.environ, {}, clear=True), \
             patch("os.path.exists", return_value=False), \
             patch("os.getcwd", return_value=str(tmp_path)):
            result = rc.generate_dut_info(
                smicli_path=str(tmp_path / "missing.exe"),
                output_file=str(tmp_path / "out.ini"),
            )
        assert result is False

    def test_sets_error_message_when_exe_not_found(self, tmp_path):
        rc = _make_runcard(tmp_path)
        with patch.dict(os.environ, {}, clear=True), \
             patch("os.path.exists", return_value=False), \
             patch("os.getcwd", return_value=str(tmp_path)):
            rc.generate_dut_info(
                smicli_path=str(tmp_path / "missing.exe"),
                output_file=str(tmp_path / "out.ini"),
            )
        assert "not found" in rc.error_message.lower()


# ══════════════════════════════════════════════════════════════════════════
# Return value: successful run
# ══════════════════════════════════════════════════════════════════════════

class TestReturnValueOnSuccess:

    def test_returns_true_on_successful_run(self, tmp_path):
        """subprocess exit 0 + valid output file → True."""
        exe = tmp_path / "SmiCli2.exe"
        exe.touch()
        out_file = tmp_path / "DUT_Info.ini"
        out_file.write_text("[info]\nos=Windows 11\n[disk_0]\nid=0\n", encoding="utf-8")

        proc = MagicMock()
        proc.returncode = 0
        proc.stderr = ""

        rc = _make_runcard(tmp_path)
        with patch("subprocess.run", return_value=proc), \
             patch("time.sleep"):          # skip the 2-second wait
            result = rc.generate_dut_info(
                smicli_path=str(exe),
                output_file=str(out_file),
                work_dir=str(tmp_path),
            )
        assert result is True

    def test_returns_false_on_nonzero_exit(self, tmp_path):
        """subprocess exit != 0 and != 3010 → False."""
        exe = tmp_path / "SmiCli2.exe"
        exe.touch()

        proc = MagicMock()
        proc.returncode = 1
        proc.stderr = "error"

        rc = _make_runcard(tmp_path)
        with patch("subprocess.run", return_value=proc):
            result = rc.generate_dut_info(
                smicli_path=str(exe),
                output_file=str(tmp_path / "out.ini"),
                work_dir=str(tmp_path),
            )
        assert result is False

    def test_returns_false_when_output_file_missing_after_run(self, tmp_path):
        """subprocess exit 0 but output file never created → False."""
        exe = tmp_path / "SmiCli2.exe"
        exe.touch()

        proc = MagicMock()
        proc.returncode = 0
        proc.stderr = ""

        rc = _make_runcard(tmp_path)
        with patch("subprocess.run", return_value=proc), \
             patch("time.sleep"):
            result = rc.generate_dut_info(
                smicli_path=str(exe),
                output_file=str(tmp_path / "nonexistent_out.ini"),
                work_dir=str(tmp_path),
            )
        assert result is False

    def test_returns_false_on_timeout(self, tmp_path):
        exe = tmp_path / "SmiCli2.exe"
        exe.touch()

        rc = _make_runcard(tmp_path)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("SmiCli2.exe", 60)):
            result = rc.generate_dut_info(
                smicli_path=str(exe),
                output_file=str(tmp_path / "out.ini"),
            )
        assert result is False
