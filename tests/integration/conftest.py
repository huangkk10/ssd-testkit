"""
Shared test configuration for all integration tests

This conftest.py provides common fixtures and configuration classes
that are inherited by all test projects under tests/integration/.

Each test project only needs to define its own testcase_config fixture,
and it will automatically get access to runcard_params and other shared fixtures.
"""

import pytest
from pathlib import Path
import re
import json

# Try to import path_manager for packaged environment support
try:
    from path_manager import path_manager
    TESTLOG_DIR = str(path_manager.get_testlog_dir())
except ImportError:
    TESTLOG_DIR = "./testlog"


class TestCaseConfiguration:
    """
    Test case configuration with clear semantic naming.
    
    This class is used across all integration tests to provide
    consistent configuration management.
    """
    
    def __init__(self, case_root_dir: Path):
        self.case_root_dir = case_root_dir
        
        # Auto-infer test case ID from directory name
        # e.g., "stc1685_burnin" -> "STC-1685"
        match = re.match(r'stc(\d+)_', case_root_dir.name)
        self.case_id = f"STC-{match.group(1)}" if match else "UNKNOWN"
        
        # Version configurations
        self.case_version = "1.0.0"
        self.autoit_version = f"{self.case_id}_v{self.case_version}"
        
        # Determine base directory for paths
        # In packaged environment: use exe directory (flat structure)
        # In development: use test case directory (original structure)
        try:
            from path_manager import path_manager
            # Packaged environment: bin/Config at exe level
            base_dir = path_manager.app_dir
        except ImportError:
            # Development environment: bin/Config in test directory
            base_dir = case_root_dir
        
        # Path configurations (works for both environments)
        self.bin_directory = base_dir / "bin"
        self.config_file = base_dir / "Config" / "Config.json"
        self.smicli_executable = base_dir / "bin/SmiCli/SmiCli2.exe"
        
        # RunCard configurations
        self.runcard_log_path = TESTLOG_DIR
        self.runcard_auto_setup = True
        
        # Log directory configurations
        self.log_directory = case_root_dir / "log"
        self.testlog_directory = case_root_dir / "testlog"
        
        # Load Config.json (tool configurations)
        self._tool_config = None
    
    @property
    def tool_config(self):
        """
        Lazy load Config.json when accessed.
        Returns the parsed JSON configuration for test tools.
        """
        if self._tool_config is None:
            if not self.config_file.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_file}")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._tool_config = json.load(f)
        
        return self._tool_config
    
    def __repr__(self):
        return (f"TestCaseConfiguration(case_id={self.case_id}, "
                f"case_version={self.case_version}, "
                f"case_root_dir={self.case_root_dir})")


@pytest.fixture(scope="session")
def runcard_params(testcase_config):
    """
    Provide RunCard initialization and start parameters.
    
    This is a shared fixture that all integration tests can use.
    It depends on the testcase_config fixture which should be defined
    in each test project's conftest.py.
    
    Returns a dictionary with RunCard-specific configuration values.
    Useful for passing to RunCard initialization and start methods.
    
    Usage:
        def test_something(runcard_params):
            runcard = Runcard(**runcard_params['initialization'])
            runcard.start_test(**runcard_params['start_params'])
    """
    return {
        # All test case configuration values (for reference)
        'case_id': testcase_config.case_id,
        'case_version': testcase_config.case_version,
        'autoit_version': testcase_config.autoit_version,
        'runcard_log_path': testcase_config.runcard_log_path,
        'bin_directory': str(testcase_config.bin_directory),
        'config_file': str(testcase_config.config_file),
        'smicli_executable': str(testcase_config.smicli_executable),
        'runcard_auto_setup': testcase_config.runcard_auto_setup,
        
        # Grouped parameters for RunCard methods
        'initialization': {
            'test_path': testcase_config.runcard_log_path,
            'test_case': testcase_config.case_id,
            'script_version': testcase_config.case_version,
        },
        'start_params': {
            'autoit_version': testcase_config.autoit_version,
            'auto_setup': testcase_config.runcard_auto_setup,
            'smicli_path': str(testcase_config.smicli_executable) if testcase_config.smicli_executable.exists() else None,
        }
    }
