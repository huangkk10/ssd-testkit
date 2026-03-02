"""
Unit tests for lib.testtool.reboot.config.
"""
import copy
import pytest

from lib.testtool.reboot.config import OsRebootConfig
from lib.testtool.reboot.exceptions import OsRebootConfigError


# ------------------------------------------------------------------ #
# get_default_config                                                   #
# ------------------------------------------------------------------ #

class TestGetDefaultConfig:
    def test_returns_dict(self):
        cfg = OsRebootConfig.get_default_config()
        assert isinstance(cfg, dict)

    def test_contains_required_keys(self):
        cfg = OsRebootConfig.get_default_config()
        for key in ('delay_seconds', 'reboot_count', 'state_file', 'abort_on_fail'):
            assert key in cfg

    def test_default_delay_seconds(self):
        assert OsRebootConfig.get_default_config()['delay_seconds'] == 10

    def test_default_reboot_count(self):
        assert OsRebootConfig.get_default_config()['reboot_count'] == 1

    def test_default_state_file(self):
        assert OsRebootConfig.get_default_config()['state_file'] == 'reboot_state.json'

    def test_default_abort_on_fail(self):
        assert OsRebootConfig.get_default_config()['abort_on_fail'] is True

    def test_returns_deep_copy(self):
        cfg1 = OsRebootConfig.get_default_config()
        cfg2 = OsRebootConfig.get_default_config()
        cfg1['delay_seconds'] = 999
        assert cfg2['delay_seconds'] != 999


# ------------------------------------------------------------------ #
# validate_config                                                      #
# ------------------------------------------------------------------ #

class TestValidateConfig:
    def test_empty_config_is_valid(self):
        assert OsRebootConfig.validate_config({}) is True

    def test_valid_full_config(self, sample_config):
        assert OsRebootConfig.validate_config(sample_config) is True

    def test_unknown_key_raises(self):
        with pytest.raises(OsRebootConfigError, match="Unknown config parameter"):
            OsRebootConfig.validate_config({'no_such_key': 1})

    @pytest.mark.parametrize("key, bad_value", [
        ('delay_seconds',  'ten'),
        ('reboot_count',   1.5),
        ('state_file',     123),
        ('abort_on_fail',  'yes'),
    ])
    def test_wrong_type_raises(self, key, bad_value):
        with pytest.raises(OsRebootConfigError, match=key):
            OsRebootConfig.validate_config({key: bad_value})

    def test_negative_delay_raises(self):
        with pytest.raises(OsRebootConfigError, match="delay_seconds"):
            OsRebootConfig.validate_config({'delay_seconds': -1})

    def test_zero_delay_is_valid(self):
        assert OsRebootConfig.validate_config({'delay_seconds': 0}) is True

    def test_zero_reboot_count_raises(self):
        with pytest.raises(OsRebootConfigError, match="reboot_count"):
            OsRebootConfig.validate_config({'reboot_count': 0})

    def test_reboot_count_one_is_valid(self):
        assert OsRebootConfig.validate_config({'reboot_count': 1}) is True


# ------------------------------------------------------------------ #
# merge_config                                                         #
# ------------------------------------------------------------------ #

class TestMergeConfig:
    def test_override_delay(self):
        base    = OsRebootConfig.get_default_config()
        merged  = OsRebootConfig.merge_config(base, {'delay_seconds': 30})
        assert merged['delay_seconds'] == 30

    def test_override_reboot_count(self):
        base   = OsRebootConfig.get_default_config()
        merged = OsRebootConfig.merge_config(base, {'reboot_count': 5})
        assert merged['reboot_count'] == 5

    def test_base_not_mutated(self):
        base    = OsRebootConfig.get_default_config()
        orig    = copy.deepcopy(base)
        OsRebootConfig.merge_config(base, {'delay_seconds': 99})
        assert base == orig

    def test_invalid_override_raises(self):
        base = OsRebootConfig.get_default_config()
        with pytest.raises(OsRebootConfigError):
            OsRebootConfig.merge_config(base, {'reboot_count': 0})

    def test_empty_override_returns_copy(self):
        base   = OsRebootConfig.get_default_config()
        merged = OsRebootConfig.merge_config(base, {})
        assert merged == base
        assert merged is not base
