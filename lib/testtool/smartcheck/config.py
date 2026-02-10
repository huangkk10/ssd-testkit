"""
SmartCheck Configuration Management

This module provides configuration management and validation for SmartCheck.
"""

from typing import Dict, Any


class SmartCheckConfig:
    """
    Configuration manager for SmartCheck parameters.
    
    This class provides:
    - Default configuration values
    - Configuration validation
    - Type conversion utilities
    """
    
    # Default configuration values matching SmartCheck.ini [global] section
    DEFAULT_CONFIG: Dict[str, Any] = {
        'total_cycle': 0,           # 0 = infinite cycles
        'total_time': 10080,        # Total time in minutes (default: 7 days)
        'dut_id': '',               # Device Under Test identifier
        'enable_monitor_smart': True,       # Enable SMART attribute monitoring
        'close_window_when_failed': False,  # Close console window on failure
        'stop_when_failed': True,           # Stop execution on failure
        'smart_config_file': 'config\\SMART.ini',  # SMART config file path
        'timeout': 60,              # Timeout in minutes (default: 1 hour)
        'check_interval': 3,        # Status check interval in seconds
    }
    
    # Valid parameter names for configuration
    VALID_PARAMS = set(DEFAULT_CONFIG.keys())
    
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
            ValueError: If configuration is invalid
        """
        for key, value in config.items():
            # Check if parameter name is valid
            if key not in SmartCheckConfig.VALID_PARAMS:
                raise ValueError(f"Invalid configuration parameter: {key}")
            
            # Validate specific parameters
            if key == 'total_cycle':
                if not isinstance(value, int) or value < 0:
                    raise ValueError(f"total_cycle must be non-negative integer, got: {value}")
            
            elif key == 'total_time':
                if not isinstance(value, int) or value <= 0:
                    raise ValueError(f"total_time must be positive integer, got: {value}")
            
            elif key == 'dut_id':
                # dut_id should be a string representing a number 0-10
                if isinstance(value, int):
                    # If int is provided, convert to string for validation
                    value_int = value
                elif isinstance(value, str):
                    try:
                        value_int = int(value)
                    except ValueError:
                        raise ValueError(f"dut_id must be a number (0-10), got: {value}")
                else:
                    raise ValueError(f"dut_id must be string or int (0-10), got type: {type(value)}")
                
                if not 0 <= value_int <= 10:
                    raise ValueError(f"dut_id must be between 0 and 10, got: {value_int}")
            
            elif key == 'timeout':
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(f"timeout must be positive number (in minutes), got: {value}")
            
            elif key == 'check_interval':
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(f"check_interval must be positive number, got: {value}")
            
            elif key in ['enable_monitor_smart', 'close_window_when_failed', 'stop_when_failed']:
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be boolean, got: {value}")
        
        return True
    
    @staticmethod
    def convert_bool_to_ini_value(value: bool) -> str:
        """
        Convert boolean value to INI format.
        
        SmartCheck.ini uses 'true'/'false' strings for boolean values.
        
        Args:
            value: Boolean value to convert
        
        Returns:
            'true' or 'false' string
        """
        return 'true' if value else 'false'
    
    @staticmethod
    def convert_ini_value_to_bool(value: str) -> bool:
        """
        Convert INI value to boolean.
        
        Args:
            value: String value from INI file
        
        Returns:
            Boolean value
        """
        return value.lower() in ('true', '1', 'yes', 'on')
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """
        Get a copy of default configuration.
        
        Returns:
            Dictionary containing default configuration values
        """
        return SmartCheckConfig.DEFAULT_CONFIG.copy()
