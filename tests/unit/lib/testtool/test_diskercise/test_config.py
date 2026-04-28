"""
Unit tests for Diskercise configuration module.
"""

import pytest
from lib.testtool.diskercise.config import DiskerciseConfig
from lib.testtool.diskercise.exceptions import DiskerciseConfigError


class TestDiskerciseConfig:
    """Test suite for DiskerciseConfig class."""

    # ----- get_default_config -----

    def test_returns_dict(self):
        config = DiskerciseConfig.get_default_config()
        assert isinstance(config, dict)

    def test_required_keys_present(self):
        config = DiskerciseConfig.get_default_config()
        required = [
            'exe_path', 'log_path', 'mode',
            'thread_count', 'file_size_mb', 'access_size_kb',
            'read_ratio', 'write_ratio', 'data_type',
            'buffered_io',
            'adv_write_signatures', 'adv_verify_immediate',
            'adv_pause_all_asap', 'adv_pulse_com1',
            'test_duration_minutes', 'check_interval_seconds',
            'window_wait_timeout', 'ui_retry_max',
        ]
        for key in required:
            assert key in config, f"Missing key: {key}"

    def test_default_test_duration(self):
        config = DiskerciseConfig.get_default_config()
        assert config['test_duration_minutes'] == 15

    def test_default_buffered_io_true(self):
        config = DiskerciseConfig.get_default_config()
        assert config['buffered_io'] is True

    def test_returns_copy(self):
        """Modifying one copy must not affect another."""
        c1 = DiskerciseConfig.get_default_config()
        c2 = DiskerciseConfig.get_default_config()
        c1['test_duration_minutes'] = 9999
        assert c2['test_duration_minutes'] != 9999

    # ----- validate_config -----

    def test_validate_valid(self, sample_config):
        assert DiskerciseConfig.validate_config(sample_config) is True

    def test_validate_empty(self):
        assert DiskerciseConfig.validate_config({}) is True

    def test_validate_unknown_key(self):
        with pytest.raises(DiskerciseConfigError):
            DiskerciseConfig.validate_config({'nonexistent_key': 1})

    def test_validate_wrong_type_int_field(self):
        with pytest.raises(DiskerciseConfigError):
            DiskerciseConfig.validate_config({'thread_count': "4"})

    def test_validate_wrong_type_bool_field(self):
        with pytest.raises(DiskerciseConfigError):
            DiskerciseConfig.validate_config({'buffered_io': 1})

    def test_validate_float_for_interval(self):
        """check_interval_seconds accepts float."""
        assert DiskerciseConfig.validate_config({'check_interval_seconds': 2.5}) is True

    def test_validate_int_for_interval(self):
        """check_interval_seconds accepts int."""
        assert DiskerciseConfig.validate_config({'check_interval_seconds': 5}) is True

    # ----- merge_config -----

    def test_merge_applies_overrides(self):
        base = DiskerciseConfig.get_default_config()
        merged = DiskerciseConfig.merge_config(base, {'thread_count': 8})
        assert merged['thread_count'] == 8

    def test_merge_preserves_base_values(self):
        base = DiskerciseConfig.get_default_config()
        original_duration = base['test_duration_minutes']
        merged = DiskerciseConfig.merge_config(base, {'thread_count': 8})
        assert merged['test_duration_minutes'] == original_duration

    def test_merge_does_not_mutate_base(self):
        base = DiskerciseConfig.get_default_config()
        DiskerciseConfig.merge_config(base, {'thread_count': 8})
        assert base['thread_count'] == DiskerciseConfig.DEFAULT_CONFIG['thread_count']

    def test_merge_rejects_invalid_overrides(self):
        base = DiskerciseConfig.get_default_config()
        with pytest.raises(DiskerciseConfigError):
            DiskerciseConfig.merge_config(base, {'bad_key': 'bad_value'})
