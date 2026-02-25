"""
Unit tests for PythonInstallerConfig.
"""

import pytest
from lib.testtool.python_installer.config import PythonInstallerConfig
from lib.testtool.python_installer.exceptions import PythonInstallerConfigError


class TestPythonInstallerConfig:
    """Test suite for PythonInstallerConfig class."""

    # ----- get_default_config -----

    def test_returns_dict(self):
        config = PythonInstallerConfig.get_default_config()
        assert isinstance(config, dict)

    def test_required_keys_present(self):
        config = PythonInstallerConfig.get_default_config()
        for key in ['version', 'architecture', 'install_path',
                    'add_to_path', 'installer_path', 'download_dir',
                    'uninstall_after_test', 'timeout_seconds',
                    'check_interval_seconds']:
            assert key in config, f"Missing key: {key}"

    def test_default_version_is_311(self):
        config = PythonInstallerConfig.get_default_config()
        assert config['version'] == '3.11'

    def test_default_architecture_is_amd64(self):
        config = PythonInstallerConfig.get_default_config()
        assert config['architecture'] == 'amd64'

    def test_returns_copy(self):
        """Modifying one copy must not affect another."""
        c1 = PythonInstallerConfig.get_default_config()
        c2 = PythonInstallerConfig.get_default_config()
        c1['version'] = '3.99'
        assert c2['version'] != '3.99'

    # ----- validate_config -----

    def test_validate_valid(self, sample_config):
        assert PythonInstallerConfig.validate_config(sample_config) is True

    def test_validate_empty(self):
        assert PythonInstallerConfig.validate_config({}) is True

    def test_validate_unknown_key(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'nonexistent_key': 1})

    def test_validate_wrong_type_timeout(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'timeout_seconds': "300"})

    def test_validate_wrong_type_add_to_path(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'add_to_path': 1})

    def test_validate_version_two_part(self):
        assert PythonInstallerConfig.validate_config({'version': '3.11'}) is True

    def test_validate_version_three_part(self):
        assert PythonInstallerConfig.validate_config({'version': '3.11.8'}) is True

    def test_validate_version_too_old(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'version': '3.5'})

    def test_validate_version_python2_rejected(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'version': '2.7'})

    def test_validate_version_bad_format(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'version': '3'})

    def test_validate_version_four_parts_rejected(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'version': '3.11.8.0'})

    def test_validate_architecture_win32(self):
        assert PythonInstallerConfig.validate_config({'architecture': 'win32'}) is True

    def test_validate_architecture_invalid(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'architecture': 'arm64'})

    def test_validate_timeout_zero_rejected(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'timeout_seconds': 0})

    def test_validate_timeout_negative_rejected(self):
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.validate_config({'timeout_seconds': -1})

    # ----- merge_config -----

    def test_merge_applies_overrides(self):
        base = PythonInstallerConfig.get_default_config()
        merged = PythonInstallerConfig.merge_config(base, {'version': '3.12'})
        assert merged['version'] == '3.12'

    def test_merge_preserves_unaffected_keys(self):
        base = PythonInstallerConfig.get_default_config()
        original_arch = base['architecture']
        merged = PythonInstallerConfig.merge_config(base, {'version': '3.12'})
        assert merged['architecture'] == original_arch

    def test_merge_does_not_mutate_base(self):
        base = PythonInstallerConfig.get_default_config()
        PythonInstallerConfig.merge_config(base, {'version': '3.12'})
        assert base['version'] == '3.11'

    def test_merge_rejects_invalid_overrides(self):
        base = PythonInstallerConfig.get_default_config()
        with pytest.raises(PythonInstallerConfigError):
            PythonInstallerConfig.merge_config(base, {'bad_key': 'bad_value'})
