"""
Unit tests for lib.testtool.osconfig.registry_helper

All winreg calls are fully mocked – no actual registry access occurs.
"""

import pytest
from unittest.mock import patch, MagicMock, call
import winreg

from lib.testtool.osconfig.registry_helper import (
    read_value,
    write_value,
    delete_value,
    key_exists,
    value_exists,
    read_value_safe,
    ensure_key,
    read_value_with_type,
    REG_DWORD,
    REG_SZ,
)
from lib.testtool.osconfig.exceptions import (
    OsConfigPermissionError,
    OsConfigActionError,
)

# Shorthand for the module under test
_MOD = "lib.testtool.osconfig.registry_helper"


# ---------------------------------------------------------------------------
# read_value()
# ---------------------------------------------------------------------------

class TestReadValue:

    @patch(f"{_MOD}.winreg.OpenKey")
    @patch(f"{_MOD}.winreg.QueryValueEx", return_value=(1, winreg.REG_DWORD))
    def test_returns_value(self, mock_query, mock_open):
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        result = read_value("HKLM", r"SOFTWARE\Test", "MyValue")
        assert result == 1

    @patch(f"{_MOD}.winreg.OpenKey", side_effect=FileNotFoundError)
    def test_raises_file_not_found(self, mock_open):
        with pytest.raises(FileNotFoundError):
            read_value("HKLM", r"SOFTWARE\Missing", "Val")

    @patch(f"{_MOD}.winreg.OpenKey", side_effect=PermissionError)
    def test_raises_permission_error(self, mock_open):
        with pytest.raises(OsConfigPermissionError):
            read_value("HKLM", r"SOFTWARE\Restricted", "Val")

    @patch(f"{_MOD}.winreg.OpenKey", side_effect=OSError("generic"))
    def test_raises_action_error_on_os_error(self, mock_open):
        with pytest.raises(OsConfigActionError):
            read_value("HKLM", r"SOFTWARE\Bad", "Val")


# ---------------------------------------------------------------------------
# write_value()
# ---------------------------------------------------------------------------

class TestWriteValue:

    @patch(f"{_MOD}.ensure_key")
    @patch(f"{_MOD}.winreg.OpenKey")
    @patch(f"{_MOD}.winreg.SetValueEx")
    def test_writes_dword(self, mock_set, mock_open, mock_ensure):
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        write_value("HKLM", r"SOFTWARE\Test", "Val", 1, REG_DWORD)
        mock_set.assert_called_once()
        mock_ensure.assert_called_once_with("HKLM", r"SOFTWARE\Test")

    @patch(f"{_MOD}.ensure_key")
    @patch(f"{_MOD}.winreg.OpenKey", side_effect=PermissionError)
    def test_raises_permission_error(self, mock_open, mock_ensure):
        with pytest.raises(OsConfigPermissionError):
            write_value("HKLM", r"SOFTWARE\Locked", "Val", 1, REG_DWORD)

    @patch(f"{_MOD}.ensure_key")
    @patch(f"{_MOD}.winreg.OpenKey", side_effect=OSError("generic"))
    def test_raises_action_error(self, mock_open, mock_ensure):
        with pytest.raises(OsConfigActionError):
            write_value("HKLM", r"SOFTWARE\Bad", "Val", 1, REG_DWORD)


# ---------------------------------------------------------------------------
# delete_value()
# ---------------------------------------------------------------------------

class TestDeleteValue:

    @patch(f"{_MOD}.winreg.OpenKey")
    @patch(f"{_MOD}.winreg.DeleteValue")
    def test_deletes_existing_value(self, mock_del, mock_open):
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        delete_value("HKLM", r"SOFTWARE\Test", "Val")
        mock_del.assert_called_once()

    @patch(f"{_MOD}.winreg.OpenKey")
    @patch(f"{_MOD}.winreg.DeleteValue", side_effect=FileNotFoundError)
    def test_no_op_when_value_missing(self, mock_del, mock_open):
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        # Must not raise
        delete_value("HKLM", r"SOFTWARE\Test", "MissingVal")

    @patch(f"{_MOD}.winreg.OpenKey", side_effect=PermissionError)
    def test_raises_permission_error(self, mock_open):
        with pytest.raises(OsConfigPermissionError):
            delete_value("HKLM", r"SOFTWARE\Locked", "Val")


# ---------------------------------------------------------------------------
# key_exists()
# ---------------------------------------------------------------------------

class TestKeyExists:

    @patch(f"{_MOD}.winreg.OpenKey")
    def test_returns_true_when_exists(self, mock_open):
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        assert key_exists("HKLM", r"SOFTWARE\Test") is True

    @patch(f"{_MOD}.winreg.OpenKey", side_effect=FileNotFoundError)
    def test_returns_false_when_missing(self, mock_open):
        assert key_exists("HKLM", r"SOFTWARE\Missing") is False

    @patch(f"{_MOD}.winreg.OpenKey", side_effect=PermissionError)
    def test_returns_true_on_permission_error(self, mock_open):
        """Key exists but we can't read it – still True."""
        assert key_exists("HKLM", r"SOFTWARE\Restricted") is True


# ---------------------------------------------------------------------------
# value_exists()
# ---------------------------------------------------------------------------

class TestValueExists:

    @patch(f"{_MOD}.read_value", return_value=1)
    def test_returns_true_when_value_exists(self, mock_read):
        assert value_exists("HKLM", r"SOFTWARE\Test", "Val") is True

    @patch(f"{_MOD}.read_value", side_effect=FileNotFoundError)
    def test_returns_false_when_value_missing(self, mock_read):
        assert value_exists("HKLM", r"SOFTWARE\Test", "Missing") is False


# ---------------------------------------------------------------------------
# read_value_safe()
# ---------------------------------------------------------------------------

class TestReadValueSafe:

    @patch(f"{_MOD}.read_value", return_value=42)
    def test_returns_value_when_exists(self, mock_read):
        assert read_value_safe("HKLM", r"SOFTWARE\Test", "Val", default=0) == 42

    @patch(f"{_MOD}.read_value", side_effect=FileNotFoundError)
    def test_returns_default_when_missing(self, mock_read):
        assert read_value_safe("HKLM", r"SOFTWARE\Test", "Missing", default=99) == 99

    @patch(f"{_MOD}.read_value", side_effect=OsConfigActionError("err"))
    def test_returns_default_on_action_error(self, mock_read):
        assert read_value_safe("HKLM", r"SOFTWARE\Test", "Val", default=None) is None


# ---------------------------------------------------------------------------
# ensure_key()
# ---------------------------------------------------------------------------

class TestEnsureKey:

    @patch(f"{_MOD}.winreg.CreateKeyEx")
    def test_creates_key(self, mock_create):
        mock_key = MagicMock()
        mock_create.return_value = mock_key
        ensure_key("HKLM", r"SOFTWARE\NewKey")
        mock_create.assert_called_once()
        mock_key.Close.assert_called_once()

    @patch(f"{_MOD}.winreg.CreateKeyEx", side_effect=PermissionError)
    def test_raises_permission_error(self, mock_create):
        with pytest.raises(OsConfigPermissionError):
            ensure_key("HKLM", r"SOFTWARE\Locked")

    @patch(f"{_MOD}.winreg.CreateKeyEx", side_effect=OSError("generic"))
    def test_raises_action_error(self, mock_create):
        with pytest.raises(OsConfigActionError):
            ensure_key("HKLM", r"SOFTWARE\Bad")


# ---------------------------------------------------------------------------
# Invalid hive
# ---------------------------------------------------------------------------

class TestInvalidHive:

    def test_unknown_hive_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown hive"):
            read_value("HKXX", r"SOFTWARE\Test", "Val")

    def test_unknown_hive_on_write(self):
        with pytest.raises(ValueError, match="Unknown hive"):
            write_value("HKXX", r"SOFTWARE\Test", "Val", 1, REG_DWORD)
