"""
Unit tests for BurnIN configuration module.
"""

import pytest
from lib.testtool.burnin.config import BurnInConfig


class TestBurnInConfig:
    """Test suite for BurnInConfig class."""
    
    def test_get_default_config(self):
        """Test getting default configuration."""
        config = BurnInConfig.get_default_config()
        
        # Check that config is a dictionary
        assert isinstance(config, dict)
        
        # Check required keys exist
        assert 'test_duration_minutes' in config
        assert 'test_drive_letter' in config
        assert 'timeout_seconds' in config
        assert 'install_path' in config
        
        # Check default values
        assert config['test_duration_minutes'] == 1440
        assert config['test_drive_letter'] == 'D'
        assert config['timeout_seconds'] == 6000
    
    def test_default_config_is_copy(self):
        """Test that get_default_config returns a copy."""
        config1 = BurnInConfig.get_default_config()
        config2 = BurnInConfig.get_default_config()
        
        # Modify config1
        config1['test_duration_minutes'] = 999
        
        # config2 should not be affected
        assert config2['test_duration_minutes'] == 1440
    
    def test_validate_valid_config(self, sample_config):
        """Test validation of valid configuration."""
        assert BurnInConfig.validate_config(sample_config) is True
    
    def test_validate_empty_config(self):
        """Test validation of empty configuration."""
        assert BurnInConfig.validate_config({}) is True
    
    def test_validate_unknown_parameter(self):
        """Test validation fails for unknown parameters."""
        config = {'unknown_parameter': 123}
        
        with pytest.raises(ValueError) as exc_info:
            BurnInConfig.validate_config(config)
        
        assert 'Unknown configuration parameter' in str(exc_info.value)
        assert 'unknown_parameter' in str(exc_info.value)
    
    def test_validate_wrong_type(self):
        """Test validation fails for wrong parameter types."""
        # test_duration_minutes should be int, not str
        config = {'test_duration_minutes': "60"}
        
        with pytest.raises(ValueError) as exc_info:
            BurnInConfig.validate_config(config)
        
        assert 'test_duration_minutes' in str(exc_info.value)
        assert 'type' in str(exc_info.value).lower()
    
    def test_validate_negative_duration(self):
        """Test validation fails for negative duration."""
        config = {'test_duration_minutes': -1}
        
        with pytest.raises(ValueError) as exc_info:
            BurnInConfig.validate_config(config)
        
        assert 'test_duration_minutes' in str(exc_info.value)
        assert '>=' in str(exc_info.value)
    
    def test_validate_excessive_duration(self):
        """Test validation fails for excessive duration."""
        config = {'test_duration_minutes': 999999}
        
        with pytest.raises(ValueError) as exc_info:
            BurnInConfig.validate_config(config)
        
        assert 'test_duration_minutes' in str(exc_info.value)
        assert '<=' in str(exc_info.value)
    
    def test_validate_invalid_drive_letter(self):
        """Test validation fails for invalid drive letters."""
        invalid_drives = ['', 'DD', '1', 'a', 'drive']
        
        for drive in invalid_drives:
            config = {'test_drive_letter': drive}
            
            with pytest.raises(ValueError) as exc_info:
                BurnInConfig.validate_config(config)
            
            assert 'test_drive_letter' in str(exc_info.value)
    
    def test_validate_valid_drive_letters(self):
        """Test validation passes for valid drive letters."""
        valid_drives = ['A', 'B', 'C', 'D', 'Z']
        
        for drive in valid_drives:
            config = {'test_drive_letter': drive}
            assert BurnInConfig.validate_config(config) is True
    
    def test_validate_timeout_constraints(self):
        """Test validation of timeout constraints."""
        # Valid values
        assert BurnInConfig.validate_config({'timeout_seconds': 0}) is True
        assert BurnInConfig.validate_config({'timeout_seconds': 3600}) is True
        assert BurnInConfig.validate_config({'timeout_seconds': 86400}) is True
        
        # Invalid: negative
        with pytest.raises(ValueError):
            BurnInConfig.validate_config({'timeout_seconds': -1})
        
        # Invalid: too large
        with pytest.raises(ValueError):
            BurnInConfig.validate_config({'timeout_seconds': 999999})
    
    def test_validate_check_interval_constraints(self):
        """Test validation of check_interval constraints."""
        # Valid values
        assert BurnInConfig.validate_config({'check_interval_seconds': 0.1}) is True
        assert BurnInConfig.validate_config({'check_interval_seconds': 2}) is True
        assert BurnInConfig.validate_config({'check_interval_seconds': 60}) is True
        
        # Invalid: too small
        with pytest.raises(ValueError):
            BurnInConfig.validate_config({'check_interval_seconds': 0})
        
        # Invalid: too large
        with pytest.raises(ValueError):
            BurnInConfig.validate_config({'check_interval_seconds': 999})
    
    def test_validate_boolean_parameters(self):
        """Test validation of boolean parameters."""
        # Valid
        assert BurnInConfig.validate_config({'enable_screenshot': True}) is True
        assert BurnInConfig.validate_config({'enable_screenshot': False}) is True
        assert BurnInConfig.validate_config({'screenshot_on_error': True}) is True
        
        # Invalid: not boolean
        with pytest.raises(ValueError):
            BurnInConfig.validate_config({'enable_screenshot': 1})
        
        with pytest.raises(ValueError):
            BurnInConfig.validate_config({'enable_screenshot': "true"})
    
    def test_merge_config(self):
        """Test configuration merging."""
        base = {
            'test_duration_minutes': 1440,
            'timeout_seconds': 6000,
            'test_drive_letter': 'D',
        }
        
        updates = {
            'test_duration_minutes': 60,
            'timeout_seconds': 300,
        }
        
        merged = BurnInConfig.merge_config(base, updates)
        
        # Updated values
        assert merged['test_duration_minutes'] == 60
        assert merged['timeout_seconds'] == 300
        
        # Preserved values
        assert merged['test_drive_letter'] == 'D'
    
    def test_merge_config_does_not_modify_original(self):
        """Test that merge_config doesn't modify original dictionaries."""
        base = {'test_duration_minutes': 1440}
        updates = {'test_duration_minutes': 60}
        
        merged = BurnInConfig.merge_config(base, updates)
        
        # Modify merged
        merged['test_duration_minutes'] = 999
        
        # Original should be unchanged
        assert base['test_duration_minutes'] == 1440
        assert updates['test_duration_minutes'] == 60
    
    def test_merge_config_with_new_keys(self):
        """Test merging configuration with new keys."""
        base = {'test_duration_minutes': 1440}
        updates = {'timeout_seconds': 300}
        
        merged = BurnInConfig.merge_config(base, updates)
        
        assert merged['test_duration_minutes'] == 1440
        assert merged['timeout_seconds'] == 300
    
    def test_validate_paths_basic(self):
        """Test basic path validation."""
        config = {
            'log_path': './testlog/burnin.log',
            'script_path': './Config/test.bits',
        }
        
        # Should pass without checking existence
        assert BurnInConfig.validate_paths(config, check_existence=False) is True
    
    def test_validate_paths_empty(self):
        """Test validation fails for empty required paths."""
        config = {'log_path': ''}
        
        with pytest.raises(ValueError) as exc_info:
            BurnInConfig.validate_paths(config, check_existence=False)
        
        assert 'log_path' in str(exc_info.value)
        assert 'empty' in str(exc_info.value).lower()
    
    def test_validate_paths_optional_empty(self):
        """Test that optional paths can be empty."""
        config = {
            'installer_path': '',
            'license_path': '',
        }
        
        # Should pass - these are optional
        assert BurnInConfig.validate_paths(config, check_existence=False) is True
    
    def test_valid_params_set(self):
        """Test that VALID_PARAMS contains all default config keys."""
        default_keys = set(BurnInConfig.DEFAULT_CONFIG.keys())
        valid_params = BurnInConfig.VALID_PARAMS
        
        assert default_keys == valid_params
    
    def test_param_types_coverage(self):
        """Test that PARAM_TYPES covers all parameters."""
        default_keys = set(BurnInConfig.DEFAULT_CONFIG.keys())
        param_types_keys = set(BurnInConfig.PARAM_TYPES.keys())
        
        # All default config keys should have type definitions
        assert default_keys == param_types_keys
