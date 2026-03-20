"""
Unit tests for windows_adk VersionAdapter.
"""

import pytest
from unittest.mock import patch

from lib.testtool.windows_adk.exceptions import ADKError
from lib.testtool.windows_adk.version_adapter import VersionAdapter


class TestVersionAdapterSupportedBuilds:
    def test_build_22000_test_dir_contains_appdata(self):
        adapter = VersionAdapter(22000, username="testuser")
        assert "AppData" in adapter.get_test_dir()
        assert "testuser" in adapter.get_test_dir()

    def test_build_22621_test_dir_uses_data_path(self):
        adapter = VersionAdapter(22621, username="testuser")
        assert r"C:\Data\Test\Microsoft\Axe\Results" in adapter.get_test_dir()

    def test_build_26100_test_dir_uses_data_path(self):
        adapter = VersionAdapter(26100, username="testuser")
        assert r"C:\Data\Test\Microsoft\Axe\Results" in adapter.get_test_dir()

    def test_build_22621_and_26100_test_dir_same(self):
        a1 = VersionAdapter(22621, username="testuser")
        a2 = VersionAdapter(26100, username="testuser")
        assert a1.get_test_dir() == a2.get_test_dir()

    def test_result_dir_contains_username(self):
        adapter = VersionAdapter(26100, username="myuser")
        assert "myuser" in adapter.get_result_dir()
        assert "Assessment Results" in adapter.get_result_dir()

    def test_job_dir_contains_username(self):
        adapter = VersionAdapter(26100, username="myuser")
        assert "myuser" in adapter.get_job_dir()
        assert "Windows Assessment Console" in adapter.get_job_dir()

    def test_os_name_returns_string(self):
        adapter = VersionAdapter(26100, username="testuser")
        assert "24H2" in adapter.os_name()

    def test_is_supported_true(self):
        adapter = VersionAdapter(22621, username="testuser")
        assert adapter.is_supported() is True


class TestVersionAdapterUnsupported:
    def test_unsupported_build_raises_adk_error(self):
        with pytest.raises(ADKError, match="Unsupported Windows build: 19041"):
            VersionAdapter(19041, username="testuser")

    def test_unsupported_build_99999_raises(self):
        with pytest.raises(ADKError):
            VersionAdapter(99999, username="testuser")


class TestVersionAdapterDefaultUsername:
    def test_defaults_to_current_user(self):
        """VersionAdapter should fall back to getpass.getuser() when no username given."""
        with patch("lib.testtool.windows_adk.version_adapter.getpass.getuser", return_value="auto_user"):
            adapter = VersionAdapter(26100)
        assert adapter.username == "auto_user"
