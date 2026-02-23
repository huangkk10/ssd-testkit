"""
Pytest configuration and fixtures for SmartCheck unit tests
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parents[6]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    """Return project root directory path"""
    return Path(__file__).resolve().parents[6]


@pytest.fixture(scope="session")
def testtool_bin_path():
    """返回測試工具 Bin directory的路徑"""
    return Path(__file__).resolve().parent.parent / "bin"


@pytest.fixture(scope="session")
def smartcheck_bat_path(testtool_bin_path):
    """Return SmartCheck.bat path"""
    return testtool_bin_path / "SmiWinTools" / "SmartCheck.bat"


@pytest.fixture(scope="session")
def smart_ini_path(testtool_bin_path):
    """Return SMART.ini path"""
    return testtool_bin_path / "SmiWinTools" / "config" / "SMART.ini"


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create independent temporary log directory for each test"""
    log_dir = tmp_path / "smartcheck_logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def smartcheck_config():
    """Return standard SmartCheck configuration"""
    return {
        'total_time': '1',  # 1 minute, for quick testing
        'dut_id': '0',
        'retryMax': 20,
        'Auto_Close': True,
        'Timeout': 120  # 2 minutes
    }


# Display environment info before testing
def pytest_configure(config):
    """Pytest configuration hook"""
    print("\n" + "="*80)
    print("SmartCheck Unit Test - Environment Check")
    print("="*80)
    
    testtool_dir = Path(__file__).resolve().parent.parent
    bin_dir = testtool_dir / "bin"
    smartcheck_bat = bin_dir / "SmiWinTools" / "SmartCheck.bat"
    smart_ini = bin_dir / "SmiWinTools" / "config" / "SMART.ini"
    
    print(f"Testtool directory: {testtool_dir}")
    print(f"Bin directory: {bin_dir}")
    print(f"  - Exists: {bin_dir.exists()}")
    print(f"SmartCheck.bat: {smartcheck_bat}")
    print(f"  - Exists: {smartcheck_bat.exists()}")
    print(f"SMART.ini: {smart_ini}")
    print(f"  - Exists: {smart_ini.exists()}")
    print("="*80 + "\n")
