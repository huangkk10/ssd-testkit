"""
Unit tests for lib.testtool.sleepstudy.config
"""

import pytest

from lib.testtool.sleepstudy.config import (
    DEFAULT_CONFIG,
    VALID_PARAMS,
    SleepStudyConfig,
    merge_config,
)
from lib.testtool.sleepstudy.exceptions import SleepStudyConfigError


class TestDefaultConfig:
    def test_output_path_default(self):
        assert DEFAULT_CONFIG["output_path"] == "sleepstudy-report.html"

    def test_timeout_default(self):
        assert DEFAULT_CONFIG["timeout"] == 60

    def test_valid_params_matches_defaults(self):
        assert VALID_PARAMS == set(DEFAULT_CONFIG.keys())


class TestMergeConfig:
    def test_no_overrides_returns_defaults(self):
        cfg = merge_config({})
        assert cfg == DEFAULT_CONFIG

    def test_override_output_path(self):
        cfg = merge_config({"output_path": "C:/tmp/report.html"})
        assert cfg["output_path"] == "C:/tmp/report.html"
        assert cfg["timeout"] == DEFAULT_CONFIG["timeout"]

    def test_override_timeout(self):
        cfg = merge_config({"timeout": 30})
        assert cfg["timeout"] == 30

    def test_unknown_key_raises(self):
        with pytest.raises(SleepStudyConfigError, match="Unknown"):
            merge_config({"bogus_key": "value"})

    def test_empty_output_path_raises(self):
        with pytest.raises(SleepStudyConfigError, match="output_path"):
            merge_config({"output_path": ""})

    def test_negative_timeout_raises(self):
        with pytest.raises(SleepStudyConfigError, match="timeout"):
            merge_config({"timeout": -1})

    def test_zero_timeout_raises(self):
        with pytest.raises(SleepStudyConfigError, match="timeout"):
            merge_config({"timeout": 0})

    def test_float_timeout_accepted(self):
        cfg = merge_config({"timeout": 30.5})
        assert cfg["timeout"] == 30.5


class TestSleepStudyConfig:
    def test_defaults(self, sample_config):
        cfg = SleepStudyConfig()
        assert cfg.output_path == DEFAULT_CONFIG["output_path"]
        assert cfg.timeout == DEFAULT_CONFIG["timeout"]

    def test_custom_values(self):
        cfg = SleepStudyConfig(output_path="C:/tmp/out.html", timeout=120)
        assert cfg.output_path == "C:/tmp/out.html"
        assert cfg.timeout == 120

    def test_repr_contains_output_path(self):
        cfg = SleepStudyConfig(output_path="my_report.html")
        assert "my_report.html" in repr(cfg)

    def test_invalid_timeout_raises(self):
        with pytest.raises(SleepStudyConfigError):
            SleepStudyConfig(timeout=-5)
