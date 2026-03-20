"""
Unit tests for windows_adk config module.
"""

import pytest
from lib.testtool.windows_adk.config import (
    DEFAULT_CONFIG,
    DEFAULT_THRESHOLDS,
    SUPPORTED_BUILDS,
    merge_config,
)


class TestDefaultThresholds:
    def test_all_threshold_keys_present(self):
        expected = {
            "FastStartup-Suspend-Overall-Time",
            "FastStartup-Resume-Overall-Time",
            "FastStartup-Resume-ReadHiberFile",
            "FastStartup-Resume-BIOS",
            "Standby-Suspend-Overall-Time",
            "Standby-Resume-Overall-Time",
        }
        assert expected == set(DEFAULT_THRESHOLDS.keys())

    def test_threshold_values_are_positive(self):
        for k, v in DEFAULT_THRESHOLDS.items():
            assert v > 0, f"Threshold {k} should be positive"


class TestSupportedBuilds:
    def test_required_builds_present(self):
        for build in (22000, 22621, 26100):
            assert build in SUPPORTED_BUILDS

    def test_build_names_are_strings(self):
        for build, name in SUPPORTED_BUILDS.items():
            assert isinstance(name, str) and len(name) > 0


class TestMergeConfig:
    def test_merge_returns_all_default_keys(self):
        result = merge_config({})
        assert set(result.keys()) == set(DEFAULT_CONFIG.keys())

    def test_merge_overrides_scalar(self):
        result = merge_config({"log_path": "./custom_log"})
        assert result["log_path"] == "./custom_log"

    def test_merge_overrides_nested_threshold(self):
        result = merge_config({"thresholds": {"FastStartup-Suspend-Overall-Time": 5}})
        assert result["thresholds"]["FastStartup-Suspend-Overall-Time"] == 5
        # Non-overridden keys should retain defaults
        assert result["thresholds"]["Standby-Resume-Overall-Time"] == DEFAULT_THRESHOLDS["Standby-Resume-Overall-Time"]

    def test_merge_does_not_mutate_default(self):
        merge_config({"log_path": "x", "thresholds": {"FastStartup-Resume-BIOS": 99}})
        assert DEFAULT_CONFIG["log_path"] == "./testlog"
        assert DEFAULT_THRESHOLDS["FastStartup-Resume-BIOS"] == 5

    def test_merge_check_result_spec_override(self):
        result = merge_config({"check_result_spec": False})
        assert result["check_result_spec"] is False
