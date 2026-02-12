"""
BurnIN Configuration Management

This module provides configuration management and validation for BurnIN.
"""

from typing import Dict, Any
from pathlib import Path


class BurnInConfig:
    """
    Configuration manager for BurnIN parameters.
    
    This class provides:
    - Default configuration values
    - Configuration validation
    - Type conversion utilities
    - Configuration merging
    
    Example:
        >>> config = BurnInConfig.get_default_config()
        >>> print(config['test_duration_minutes'])
        1440
        >>> BurnInConfig.validate_config({'test_duration_minutes': 60})
        True
    """
    
    # Default configuration values
    DEFAULT_CONFIG: Dict[str, Any] = {
        # Installation paths
        'installer_path': '',
        'license_path': '',
        'install_path': 'C:\\Program Files\\BurnInTest',
        'executable_name': 'bit.exe',  # or 'bit64.exe'
        
        # Script and configuration paths
        'script_path': './Config/BIT_Config/BurnInScript.bits',
        'config_file_path': './Config/BIT_Config/BurnInScript.bitcfg',
        
        # Test parameters
        'test_duration_minutes': 1440,  # 24 hours default
        'test_drive_letter': 'D',
        
        # Logging
        'log_path': './testlog/Burnin.log',
        'log_prefix': '',
        
        # Execution control
        'timeout_minutes': 100,  # 100 minutes
        'check_interval_seconds': 2,
        'ui_retry_max': 60,
        'ui_retry_interval_seconds': 3,
        
        # Process monitoring
        'enable_screenshot': True,
        'screenshot_on_error': True,
    }
    
    # Valid parameter names
    VALID_PARAMS = set(DEFAULT_CONFIG.keys())
    
    # Type mapping for validation
    PARAM_TYPES: Dict[str, type] = {
        'installer_path': str,
        'license_path': str,
        'install_path': str,
        'executable_name': str,
        'script_path': str,
        'config_file_path': str,
        'test_duration_minutes': int,
        'test_drive_letter': str,
        'log_path': str,
        'log_prefix': str,
        'timeout_minutes': (int, float),
        'check_interval_seconds': (int, float),
        'ui_retry_max': int,
        'ui_retry_interval_seconds': (int, float),
        'enable_screenshot': bool,
        'screenshot_on_error': bool,
    }
    
    # Value constraints
    PARAM_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
        'test_duration_minutes': {'min': 0, 'max': 10080},  # 0-7 days
        'timeout_minutes': {'min': 1, 'max': 1440},  # 1-1440 minutes (1 day)
        'check_interval_seconds': {'min': 0.1, 'max': 60},
        'ui_retry_max': {'min': 1, 'max': 300},
        'ui_retry_interval_seconds': {'min': 0.1, 'max': 60},
        'test_drive_letter': {'pattern': r'^[A-Z]$'},
    }
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """
        Validate configuration dictionary.
        
        Checks:
        - Parameter names are valid
        - Parameter types are correct
        - Parameter values are within acceptable ranges
        
        Args:
            config: Configuration dictionary to validate
        
        Returns:
            True if configuration is valid
        
        Raises:
            ValueError: If validation fails with detailed error message
        
        Example:
            >>> BurnInConfig.validate_config({'test_duration_minutes': 60})
            True
            >>> BurnInConfig.validate_config({'test_duration_minutes': -1})
            Traceback (most recent call last):
            ...
            ValueError: test_duration_minutes must be >= 0
        """
        for key, value in config.items():
            # Check if parameter name is valid
            if key not in BurnInConfig.VALID_PARAMS:
                raise ValueError(f"Unknown configuration parameter: {key}")
            
            # Check type
            expected_type = BurnInConfig.PARAM_TYPES.get(key)
            if expected_type is not None:
                if isinstance(expected_type, tuple):
                    if not isinstance(value, expected_type):
                        raise ValueError(
                            f"{key} must be one of types {expected_type}, got {type(value).__name__}"
                        )
                else:
                    if not isinstance(value, expected_type):
                        raise ValueError(
                            f"{key} must be of type {expected_type.__name__}, got {type(value).__name__}"
                        )
            
            # Check constraints
            if key in BurnInConfig.PARAM_CONSTRAINTS:
                constraints = BurnInConfig.PARAM_CONSTRAINTS[key]
                
                # Min/max constraints
                if 'min' in constraints and value < constraints['min']:
                    raise ValueError(f"{key} must be >= {constraints['min']}")
                if 'max' in constraints and value > constraints['max']:
                    raise ValueError(f"{key} must be <= {constraints['max']}")
                
                # Pattern constraints
                if 'pattern' in constraints:
                    import re
                    if not re.match(constraints['pattern'], str(value)):
                        raise ValueError(
                            f"{key} must match pattern {constraints['pattern']}"
                        )
        
        return True
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """
        Get a copy of default configuration.
        
        Returns:
            Dict[str, Any]: Copy of default configuration dictionary
        
        Example:
            >>> config = BurnInConfig.get_default_config()
            >>> config['test_duration_minutes']
            1440
            >>> config['test_duration_minutes'] = 60  # Modify copy
            >>> BurnInConfig.get_default_config()['test_duration_minutes']
            1440
        """
        return BurnInConfig.DEFAULT_CONFIG.copy()
    
    @staticmethod
    def merge_config(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge configuration dictionaries.
        
        Updates are applied to base, base values are preserved if not in updates.
        
        Args:
            base: Base configuration dictionary
            updates: Updates to apply
        
        Returns:
            Dict[str, Any]: Merged configuration dictionary
        
        Example:
            >>> base = {'test_duration_minutes': 1440, 'timeout_seconds': 6000}
            >>> updates = {'test_duration_minutes': 60}
            >>> merged = BurnInConfig.merge_config(base, updates)
            >>> merged['test_duration_minutes']
            60
            >>> merged['timeout_seconds']
            6000
        """
        merged = base.copy()
        merged.update(updates)
        return merged
    
    @staticmethod
    def validate_paths(config: Dict[str, Any], check_existence: bool = False) -> bool:
        """
        Validate path configurations.
        
        Args:
            config: Configuration dictionary
            check_existence: If True, check if paths actually exist
        
        Returns:
            True if all paths are valid
        
        Raises:
            ValueError: If path validation fails
        
        Example:
            >>> config = {'installer_path': './bin/BurnIn/installer.exe'}
            >>> BurnInConfig.validate_paths(config, check_existence=False)
            True
        """
        path_params = [
            'installer_path',
            'license_path',
            'install_path',
            'script_path',
            'config_file_path',
            'log_path',
        ]
        
        for param in path_params:
            if param in config:
                path_value = config[param]
                
                # Check if path is not empty (except for optional paths)
                optional_paths = ['installer_path', 'license_path']
                if not path_value and param not in optional_paths:
                    raise ValueError(f"{param} cannot be empty")
                
                # Check existence if requested
                if check_existence and path_value:
                    path = Path(path_value)
                    if not path.exists():
                        raise ValueError(f"{param} does not exist: {path_value}")
        
        return True
