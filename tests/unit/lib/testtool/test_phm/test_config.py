"""
Unit tests for PHM configuration module.
"""

import pytest
from lib.testtool.phm.config import PHMConfig
from lib.testtool.phm.exceptions import PHMConfigError


class TestPHMConfig:
    """Test suite for PHMConfig class."""

    # ------------------------------------------------------------------
    # get_default_config
    # ------------------------------------------------------------------

    def test_returns_dict(self):
        config = PHMConfig.get_default_config()
        assert isinstance(config, dict)

    def test_required_keys_present(self):
        config = PHMConfig.get_default_config()
        required = [
            'installer_path',
            'install_path',
            'executable_name',
            'cycle_count',
            'test_duration_minutes',
            'enable_modern_standby',
            'log_path',
            'timeout',
            'check_interval_seconds',
        ]
        for key in required:
            assert key in config, f"Missing required key: {key}"

    def test_returns_independent_copy(self):
        """Modifying one copy must not affect another."""
        c1 = PHMConfig.get_default_config()
        c2 = PHMConfig.get_default_config()
        c1['cycle_count'] = 9999
        assert c2['cycle_count'] != 9999

    def test_default_cycle_count(self):
        assert PHMConfig.get_default_config()['cycle_count'] == 10

    def test_default_enable_modern_standby(self):
        assert PHMConfig.get_default_config()['enable_modern_standby'] is True

    # ------------------------------------------------------------------
    # validate_config
    # ------------------------------------------------------------------

    def test_validate_valid(self, sample_config):
        assert PHMConfig.validate_config(sample_config) is True

    def test_validate_empty(self):
        assert PHMConfig.validate_config({}) is True

    def test_validate_unknown_key(self):
        with pytest.raises(PHMConfigError, match="Unknown config parameter"):
            PHMConfig.validate_config({'nonexistent_key': 1})

    def test_validate_wrong_type_cycle_count(self):
        with pytest.raises(PHMConfigError):
            PHMConfig.validate_config({'cycle_count': "10"})  # must be int

    def test_validate_wrong_type_timeout(self):
        with pytest.raises(PHMConfigError):
            PHMConfig.validate_config({'timeout': "3600"})  # must be int/float

    def test_validate_wrong_type_enable_modern_standby(self):
        with pytest.raises(PHMConfigError):
            PHMConfig.validate_config({'enable_modern_standby': 1})  # must be bool

    def test_validate_wrong_type_installer_path(self):
        with pytest.raises(PHMConfigError):
            PHMConfig.validate_config({'installer_path': 123})  # must be str

    # ------------------------------------------------------------------
    # merge_config
    # ------------------------------------------------------------------

    def test_merge_applies_override(self):
        base = PHMConfig.get_default_config()
        merged = PHMConfig.merge_config(base, {'cycle_count': 99})
        assert merged['cycle_count'] == 99

    def test_merge_preserves_non_overridden(self):
        base = PHMConfig.get_default_config()
        original_log_path = base['log_path']
        merged = PHMConfig.merge_config(base, {'cycle_count': 99})
        assert merged['log_path'] == original_log_path

    def test_merge_does_not_mutate_base(self):
        base = PHMConfig.get_default_config()
        original = base['cycle_count']
        PHMConfig.merge_config(base, {'cycle_count': 999})
        assert base['cycle_count'] == original

    def test_merge_rejects_unknown_key(self):
        base = PHMConfig.get_default_config()
        with pytest.raises(PHMConfigError):
            PHMConfig.merge_config(base, {'bad_key': 'bad_value'})

    def test_merge_multiple_overrides(self):
        base = PHMConfig.get_default_config()
        merged = PHMConfig.merge_config(base, {
            'cycle_count': 20,
            'enable_modern_standby': False,
            'timeout': 1800,
        })
        assert merged['cycle_count'] == 20
        assert merged['enable_modern_standby'] is False
        assert merged['timeout'] == 1800
