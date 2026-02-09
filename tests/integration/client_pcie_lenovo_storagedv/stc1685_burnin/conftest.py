"""
Test configuration for STC-1685 BurnIN test

This conftest.py provides centralized configuration for the test case.
Configuration values can be automatically inferred from directory structure.
"""

import pytest
from pathlib import Path
import re
import json


class TestCaseConfiguration:
    """Test case configuration with clear semantic naming"""
    
    def __init__(self, case_root_dir: Path):
        self.case_root_dir = case_root_dir
        
        # Auto-infer test case ID from directory name
        # e.g., "stc1685_burnin" -> "STC-1685"
        match = re.match(r'stc(\d+)_', case_root_dir.name)
        self.case_id = f"STC-{match.group(1)}" if match else "UNKNOWN"
        
        # Version configurations
        self.case_version = "1.0.0"
        self.autoit_version = f"{self.case_id}_v{self.case_version}"
        
        # Path configurations
        self.bin_directory = case_root_dir / "bin"
        self.config_file = case_root_dir / "Config" / "Config.json"
        self.smicli_executable = case_root_dir / "bin/SmiCli/SmiCli2.exe"
        
        # RunCard configurations
        self.runcard_log_path = "./testlog"
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
def testcase_config():
    """
    Provide test case configuration as a fixture.
    
    Automatically infers configuration from directory structure.
    Can be overridden in specific tests if needed.
    
    Usage in test:
        def test_something(testcase_config):
            print(testcase_config.case_id)  # "STC-1685"
            print(testcase_config.case_version)  # "1.0.0"
    """
    case_root_dir = Path(__file__).parent
    config = TestCaseConfiguration(case_root_dir)
    return config


@pytest.fixture(scope="session")
def runcard_params(testcase_config):
    """
    Provide RunCard initialization and start parameters.
    
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
