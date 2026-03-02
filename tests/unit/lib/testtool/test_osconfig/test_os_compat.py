"""
Unit tests for lib.testtool.osconfig.os_compat

All registry access and platform calls are mocked so these tests run
without Administrator privileges and on non-Windows CI agents.
"""

import pytest
from unittest.mock import patch, MagicMock

from lib.testtool.osconfig.os_compat import (
    WindowsBuildInfo,
    CAPABILITIES,
    get_build_info,
    is_supported,
    get_capability_description,
    list_unsupported_features,
    _detect_edition,
)


# ---------------------------------------------------------------------------
# WindowsBuildInfo dataclass
# ---------------------------------------------------------------------------

class TestWindowsBuildInfo:

    def test_fields_accessible(self, win10_build):
        assert win10_build.major == 10
        assert win10_build.build == 19045
        assert win10_build.edition == "Pro"
        assert win10_build.version_tag == "win10"
        assert win10_build.product_name == "Windows 10 Pro"

    def test_win11_tag(self, win11_build):
        assert win11_build.version_tag == "win11"
        assert win11_build.build >= 22000


# ---------------------------------------------------------------------------
# _detect_edition helper
# ---------------------------------------------------------------------------

class TestDetectEdition:

    @pytest.mark.parametrize("product_name, expected", [
        ("Windows 10 Home",                    "Home"),
        ("Windows 10 Pro",                     "Pro"),
        ("Windows 10 Enterprise",              "Enterprise"),
        ("Windows 10 Education",               "Education"),
        ("Windows Server 2022 Datacenter",     "Server"),
        ("Windows 11 Pro",                     "Pro"),
        ("Windows 11 Enterprise",              "Enterprise"),
        ("Something Completely Unknown",       "Unknown"),
    ])
    def test_edition_detection(self, product_name, expected):
        assert _detect_edition(product_name) == expected


# ---------------------------------------------------------------------------
# get_build_info() – mocked registry reads
# ---------------------------------------------------------------------------

_REG_VALUES = {
    "ProductName":  "Windows 10 Pro",
    "CurrentBuild": "19045",
}


def _fake_read_registry_str(key_path, value_name):
    return _REG_VALUES[value_name]


class TestGetBuildInfo:

    @patch("lib.testtool.osconfig.os_compat._read_registry_str",
           side_effect=_fake_read_registry_str)
    def test_returns_build_info(self, mock_reg):
        info = get_build_info()
        assert isinstance(info, WindowsBuildInfo)
        assert info.build == 19045
        assert info.edition == "Pro"
        assert info.version_tag == "win10"

    @patch("lib.testtool.osconfig.os_compat._read_registry_str",
           side_effect=_fake_read_registry_str)
    def test_win11_tag_at_build_22000(self, mock_reg):
        _REG_VALUES["CurrentBuild"] = "22621"
        _REG_VALUES["ProductName"]  = "Windows 10 Pro"
        try:
            info = get_build_info()
            assert info.version_tag == "win11"
            assert "Windows 11" in info.product_name
        finally:
            _REG_VALUES["CurrentBuild"] = "19045"
            _REG_VALUES["ProductName"]  = "Windows 10 Pro"

    @patch("lib.testtool.osconfig.os_compat._read_registry_str",
           side_effect=OSError("permission denied"))
    def test_registry_failure_returns_sentinel(self, mock_reg):
        """On registry failure a sentinel with build=0 is returned, not an exception."""
        info = get_build_info()
        assert info.build == 0
        assert info.version_tag == "unknown"


# ---------------------------------------------------------------------------
# is_supported() – Capability Matrix checks
# ---------------------------------------------------------------------------

class TestIsSupported:

    def test_unknown_feature_raises_key_error(self, win10_build):
        with pytest.raises(KeyError, match="Unknown capability"):
            is_supported("nonexistent_feature", win10_build)

    def test_search_index_supported_everywhere(self, win10_build, win11_build):
        assert is_supported("search_index", win10_build) is True
        assert is_supported("search_index", win11_build) is True

    def test_search_index_excluded_on_server(self, win_server_build):
        assert is_supported("search_index", win_server_build) is False

    def test_onedrive_metered_requires_rs1(self, win10_home_build):
        """Build 10586 (pre-RS1) must NOT support onedrive_metered."""
        assert is_supported("onedrive_metered", win10_home_build) is False

    def test_onedrive_metered_supported_on_rs1_plus(self, win10_build):
        """Build 19045 (RS1+) must support onedrive_metered."""
        assert is_supported("onedrive_metered", win10_build) is True

    def test_tamper_protection_api_requires_1903(self, win10_pre_tamper_build):
        """Build 17763 (1809) predates Tamper Protection API."""
        assert is_supported("defender_tamper_protection_api", win10_pre_tamper_build) is False

    def test_tamper_protection_api_on_1903(self, win10_post_tamper_build):
        """Build 18362 (1903) introduced Tamper Protection API."""
        assert is_supported("defender_tamper_protection_api", win10_post_tamper_build) is True

    def test_system_restore_excluded_on_server(self, win_server_build):
        assert is_supported("system_restore", win_server_build) is False

    def test_all_features_covered_in_capabilities(self):
        """Every key in CAPABILITIES should be a non-empty string."""
        for key in CAPABILITIES:
            assert isinstance(key, str) and len(key) > 0


# ---------------------------------------------------------------------------
# get_capability_description()
# ---------------------------------------------------------------------------

class TestGetCapabilityDescription:

    def test_known_feature_returns_string(self):
        desc = get_capability_description("search_index")
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_unknown_feature_raises_key_error(self):
        with pytest.raises(KeyError):
            get_capability_description("does_not_exist")


# ---------------------------------------------------------------------------
# list_unsupported_features()
# ---------------------------------------------------------------------------

class TestListUnsupportedFeatures:

    def test_old_build_has_unsupported(self, win10_home_build):
        unsupported = list_unsupported_features(win10_home_build)
        assert "onedrive_metered" in unsupported
        assert "onedrive_filesync" in unsupported

    def test_server_has_unsupported(self, win_server_build):
        unsupported = list_unsupported_features(win_server_build)
        assert "search_index" in unsupported
        assert "system_restore" in unsupported

    def test_modern_pro_has_few_unsupported(self, win11_build):
        unsupported = list_unsupported_features(win11_build)
        # Modern Win11 Pro should support almost everything
        assert "search_index" not in unsupported
        assert "onedrive_metered" not in unsupported

    def test_returns_list(self, win10_build):
        result = list_unsupported_features(win10_build)
        assert isinstance(result, list)
