"""
Unit tests for CDI configuration module.
"""

import pytest
from lib.testtool.cdi.config import CDIConfig
from lib.testtool.cdi.exceptions import CDIConfigError


class TestCDIConfig:
    """Test suite for CDIConfig class."""

    # ----- get_default_config -----

    def test_returns_dict(self):
        config = CDIConfig.get_default_config()
        assert isinstance(config, dict)

    def test_required_keys_present(self):
        config = CDIConfig.get_default_config()
        for key in [
            'executable_path', 'log_path', 'log_prefix',
            'timeout_seconds', 'diskinfo_txt_name', 'diskinfo_json_name',
        ]:
            assert key in config, f"Missing key: {key}"

    def test_default_executable_path(self):
        config = CDIConfig.get_default_config()
        assert 'DiskInfo64.exe' in config['executable_path']

    def test_default_timeout(self):
        config = CDIConfig.get_default_config()
        assert config['timeout_seconds'] == 300

    def test_returns_copy(self):
        """Modifying one copy must not affect another."""
        c1 = CDIConfig.get_default_config()
        c2 = CDIConfig.get_default_config()
        c1['timeout_seconds'] = 9999
        assert c2['timeout_seconds'] != 9999

    # ----- validate_config -----

    def test_validate_valid(self, sample_config):
        assert CDIConfig.validate_config(sample_config) is True

    def test_validate_empty(self):
        assert CDIConfig.validate_config({}) is True

    def test_validate_unknown_key(self):
        with pytest.raises(CDIConfigError):
            CDIConfig.validate_config({'nonexistent_key': 1})

    def test_validate_wrong_type_timeout(self):
        with pytest.raises(CDIConfigError):
            CDIConfig.validate_config({'timeout_seconds': '60'})

    def test_validate_wrong_type_log_path(self):
        with pytest.raises(CDIConfigError):
            CDIConfig.validate_config({'log_path': 123})

    def test_validate_wrong_type_save_retry_max(self):
        with pytest.raises(CDIConfigError):
            CDIConfig.validate_config({'save_retry_max': 5.5})

    # ----- merge_config -----

    def test_merge_applies_override(self):
        base = CDIConfig.get_default_config()
        merged = CDIConfig.merge_config(base, {'timeout_seconds': 999})
        assert merged['timeout_seconds'] == 999

    def test_merge_preserves_other_keys(self):
        base = CDIConfig.get_default_config()
        orig_log = base['log_path']
        merged = CDIConfig.merge_config(base, {'timeout_seconds': 999})
        assert merged['log_path'] == orig_log

    def test_merge_does_not_mutate_base(self):
        base = CDIConfig.get_default_config()
        CDIConfig.merge_config(base, {'timeout_seconds': 999})
        assert base['timeout_seconds'] == 300

    def test_merge_rejects_invalid_key(self):
        base = CDIConfig.get_default_config()
        with pytest.raises(CDIConfigError):
            CDIConfig.merge_config(base, {'invalid_key': 'value'})

    def test_merge_multiple_overrides(self):
        base = CDIConfig.get_default_config()
        merged = CDIConfig.merge_config(base, {
            'log_prefix': 'Before_',
            'screenshot_drive_letter': 'C:',
        })
        assert merged['log_prefix'] == 'Before_'
        assert merged['screenshot_drive_letter'] == 'C:'
