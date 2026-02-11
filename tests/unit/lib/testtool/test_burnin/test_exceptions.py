"""
Unit tests for BurnIN exceptions module.
"""

import pytest
from lib.testtool.burnin.exceptions import (
    BurnInError,
    BurnInConfigError,
    BurnInTimeoutError,
    BurnInProcessError,
    BurnInInstallError,
    BurnInUIError,
    BurnInTestFailedError,
)


class TestBurnInExceptions:
    """Test suite for BurnIN exception classes."""
    
    def test_base_exception(self):
        """Test BurnInError base exception."""
        with pytest.raises(BurnInError):
            raise BurnInError("Base error")
        
        # Test message
        try:
            raise BurnInError("Test message")
        except BurnInError as e:
            assert str(e) == "Test message"
    
    def test_config_error(self):
        """Test BurnInConfigError exception."""
        with pytest.raises(BurnInConfigError):
            raise BurnInConfigError("Config error")
        
        # Test inheritance
        with pytest.raises(BurnInError):
            raise BurnInConfigError("Config error")
    
    def test_timeout_error(self):
        """Test BurnInTimeoutError exception."""
        with pytest.raises(BurnInTimeoutError):
            raise BurnInTimeoutError("Timeout error")
        
        # Test inheritance
        with pytest.raises(BurnInError):
            raise BurnInTimeoutError("Timeout error")
    
    def test_process_error(self):
        """Test BurnInProcessError exception."""
        with pytest.raises(BurnInProcessError):
            raise BurnInProcessError("Process error")
        
        # Test inheritance
        with pytest.raises(BurnInError):
            raise BurnInProcessError("Process error")
    
    def test_install_error(self):
        """Test BurnInInstallError exception."""
        with pytest.raises(BurnInInstallError):
            raise BurnInInstallError("Install error")
        
        # Test inheritance
        with pytest.raises(BurnInError):
            raise BurnInInstallError("Install error")
    
    def test_ui_error(self):
        """Test BurnInUIError exception."""
        with pytest.raises(BurnInUIError):
            raise BurnInUIError("UI error")
        
        # Test inheritance
        with pytest.raises(BurnInError):
            raise BurnInUIError("UI error")
    
    def test_test_failed_error(self):
        """Test BurnInTestFailedError exception."""
        with pytest.raises(BurnInTestFailedError):
            raise BurnInTestFailedError("Test failed")
        
        # Test inheritance
        with pytest.raises(BurnInError):
            raise BurnInTestFailedError("Test failed")
    
    def test_exception_hierarchy(self):
        """Test that all exceptions inherit from BurnInError."""
        exceptions = [
            BurnInConfigError,
            BurnInTimeoutError,
            BurnInProcessError,
            BurnInInstallError,
            BurnInUIError,
            BurnInTestFailedError,
        ]
        
        for exc_class in exceptions:
            assert issubclass(exc_class, BurnInError)
            assert issubclass(exc_class, Exception)
    
    def test_catch_specific_exception(self):
        """Test catching specific exception types."""
        def raise_config_error():
            raise BurnInConfigError("Config error")
        
        # Catch specific type
        with pytest.raises(BurnInConfigError):
            raise_config_error()
        
        # Also caught by base type
        with pytest.raises(BurnInError):
            raise_config_error()
    
    def test_exception_with_details(self):
        """Test exceptions with detailed error messages."""
        error_details = {
            'parameter': 'test_duration_minutes',
            'value': -1,
            'reason': 'must be >= 0'
        }
        
        error_msg = f"Invalid parameter '{error_details['parameter']}': " \
                   f"value {error_details['value']} {error_details['reason']}"
        
        try:
            raise BurnInConfigError(error_msg)
        except BurnInConfigError as e:
            assert 'test_duration_minutes' in str(e)
            assert '-1' in str(e)
            assert 'must be >= 0' in str(e)
