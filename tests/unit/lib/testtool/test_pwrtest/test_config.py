"""
Unit tests for PwrTest configuration module.
"""

import warnings
import pytest
from lib.testtool.pwrtest.config import PwrTestConfig, KNOWN_OS_VERSIONS
from lib.testtool.pwrtest.exceptions import PwrTestConfigError


class TestPwrTestConfig:
    """Test suite for PwrTestConfig class."""

    # ------------------------------------------------------------------ #
    # get_default_config                                                   #
    # ------------------------------------------------------------------ #

    def test_returns_dict(self):
        assert isinstance(PwrTestConfig.get_default_config(), dict)

    def test_required_keys_present(self):
        cfg = PwrTestConfig.get_default_config()
        for key in [
            'executable_path', 'pwrtest_base_dir',
            'os_name', 'os_version',
            'cycle_count', 'delay_seconds', 'wake_after_seconds',
            'log_path', 'timeout_seconds', 'check_interval_seconds',
        ]:
            assert key in cfg, f"Missing key: {key}"

    def test_returns_independent_copy(self):
        c1 = PwrTestConfig.get_default_config()
        c2 = PwrTestConfig.get_default_config()
        c1['cycle_count'] = 999
        assert c2['cycle_count'] != 999

    def test_default_os_name(self):
        assert PwrTestConfig.get_default_config()['os_name'] == 'win11'

    def test_default_os_version(self):
        assert PwrTestConfig.get_default_config()['os_version'] == '25H2'

    def test_default_cycle_count(self):
        assert PwrTestConfig.get_default_config()['cycle_count'] == 1

    # ------------------------------------------------------------------ #
    # validate_config                                                      #
    # ------------------------------------------------------------------ #

    def test_validate_empty(self):
        assert PwrTestConfig.validate_config({}) is True

    def test_validate_valid_overrides(self, sample_config):
        assert PwrTestConfig.validate_config(sample_config) is True

    def test_validate_unknown_key(self):
        with pytest.raises(PwrTestConfigError, match="Unknown config parameter"):
            PwrTestConfig.validate_config({'nonexistent_key': 1})

    def test_validate_wrong_type_cycle_count(self):
        with pytest.raises(PwrTestConfigError):
            PwrTestConfig.validate_config({'cycle_count': '1'})  # str, not int

    def test_validate_wrong_type_timeout(self):
        with pytest.raises(PwrTestConfigError):
            PwrTestConfig.validate_config({'timeout_seconds': 60.5})  # float, not int

    def test_validate_invalid_os_name(self):
        with pytest.raises(PwrTestConfigError, match="os_name"):
            PwrTestConfig.validate_config({'os_name': 'winXP'})

    def test_validate_valid_os_names(self):
        for os_name in ('win7', 'win10', 'win11'):
            assert PwrTestConfig.validate_config({'os_name': os_name}) is True

    def test_validate_zero_cycle_count_raises(self):
        with pytest.raises(PwrTestConfigError, match="cycle_count"):
            PwrTestConfig.validate_config({'cycle_count': 0})

    def test_validate_negative_delay_raises(self):
        with pytest.raises(PwrTestConfigError, match="delay_seconds"):
            PwrTestConfig.validate_config({'delay_seconds': -5})

    def test_validate_zero_wake_after_raises(self):
        with pytest.raises(PwrTestConfigError, match="wake_after_seconds"):
            PwrTestConfig.validate_config({'wake_after_seconds': 0})

    def test_validate_timeout_too_short_warns(self):
        # cycle(1) * (delay(10) + wake(30)) = 40 — timeout of 40 should warn
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            PwrTestConfig.validate_config({
                'cycle_count': 1,
                'delay_seconds': 10,
                'wake_after_seconds': 30,
                'timeout_seconds': 40,
            })
        assert any(issubclass(w.category, UserWarning) for w in caught)

    def test_validate_unknown_os_version_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            PwrTestConfig.validate_config({'os_name': 'win11', 'os_version': 'FUTURE_H2'})
        assert any(issubclass(w.category, UserWarning) for w in caught)

    def test_validate_known_os_version_no_warn(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            PwrTestConfig.validate_config({'os_name': 'win11', 'os_version': '25H2'})
        version_warns = [
            w for w in caught
            if issubclass(w.category, UserWarning) and 'os_version' in str(w.message)
        ]
        assert len(version_warns) == 0

    # ------------------------------------------------------------------ #
    # merge_config                                                         #
    # ------------------------------------------------------------------ #

    def test_merge_applies_override(self):
        base = PwrTestConfig.get_default_config()
        merged = PwrTestConfig.merge_config(base, {'cycle_count': 5})
        assert merged['cycle_count'] == 5

    def test_merge_preserves_unrelated_keys(self):
        base = PwrTestConfig.get_default_config()
        merged = PwrTestConfig.merge_config(base, {'cycle_count': 3})
        assert merged['os_name'] == base['os_name']
        assert merged['log_path'] == base['log_path']

    def test_merge_does_not_mutate_base(self):
        base = PwrTestConfig.get_default_config()
        original_count = base['cycle_count']
        PwrTestConfig.merge_config(base, {'cycle_count': 99})
        assert base['cycle_count'] == original_count

    def test_merge_rejects_invalid_overrides(self):
        base = PwrTestConfig.get_default_config()
        with pytest.raises(PwrTestConfigError):
            PwrTestConfig.merge_config(base, {'bad_key': 'bad_value'})

    # ------------------------------------------------------------------ #
    # resolve_executable_path                                              #
    # ------------------------------------------------------------------ #

    def test_resolve_exact_path_used_when_set(self):
        cfg = PwrTestConfig.get_default_config()
        cfg['executable_path'] = 'C:/custom/pwrtest.exe'
        from pathlib import Path
        assert PwrTestConfig.resolve_executable_path(cfg) == Path('C:/custom/pwrtest.exe')

    def test_resolve_auto_combines_parts(self):
        cfg = PwrTestConfig.get_default_config()
        cfg['executable_path'] = ''
        cfg['pwrtest_base_dir'] = './bin/pwrtest'
        cfg['os_name'] = 'win10'
        cfg['os_version'] = '2004'
        from pathlib import Path
        expected = Path('./bin/pwrtest/win10/2004/pwrtest.exe')
        assert PwrTestConfig.resolve_executable_path(cfg) == expected

    # ------------------------------------------------------------------ #
    # get_supported_os_versions                                            #
    # ------------------------------------------------------------------ #

    def test_get_supported_os_versions_returns_dict(self):
        result = PwrTestConfig.get_supported_os_versions()
        assert isinstance(result, dict)

    def test_get_supported_os_versions_copy(self):
        r1 = PwrTestConfig.get_supported_os_versions()
        r1['win11'].append('99H2')
        r2 = PwrTestConfig.get_supported_os_versions()
        assert '99H2' not in r2['win11']

    def test_win11_versions_known(self):
        versions = PwrTestConfig.get_supported_os_versions()['win11']
        for v in ('21H2', '22H2', '24H2', '25H2'):
            assert v in versions

    def test_win10_versions_known(self):
        versions = PwrTestConfig.get_supported_os_versions()['win10']
        for v in ('1709', '2004'):
            assert v in versions
