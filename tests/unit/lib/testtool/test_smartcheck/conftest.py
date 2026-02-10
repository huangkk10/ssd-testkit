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
    """返回專案根目錄路徑"""
    return Path(__file__).resolve().parents[6]


@pytest.fixture(scope="session")
def testtool_bin_path():
    """返回測試工具 bin 目錄的路徑"""
    return Path(__file__).resolve().parent.parent / "bin"


@pytest.fixture(scope="session")
def smartcheck_bat_path(testtool_bin_path):
    """返回 SmartCheck.bat 的路徑"""
    return testtool_bin_path / "SmiWinTools" / "SmartCheck.bat"


@pytest.fixture(scope="session")
def smart_ini_path(testtool_bin_path):
    """返回 SMART.ini 的路徑"""
    return testtool_bin_path / "SmiWinTools" / "config" / "SMART.ini"


@pytest.fixture
def temp_log_dir(tmp_path):
    """為每個測試創建獨立的臨時 log 目錄"""
    log_dir = tmp_path / "smartcheck_logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def smartcheck_config():
    """返回標準的 SmartCheck 配置"""
    return {
        'total_time': '1',  # 1 分鐘，用於快速測試
        'dut_id': '0',
        'retryMax': 20,
        'Auto_Close': True,
        'Timeout': 120  # 2 分鐘
    }


# 在測試開始前顯示環境信息
def pytest_configure(config):
    """Pytest 配置鉤子"""
    print("\n" + "="*80)
    print("SmartCheck Unit Test - 環境檢查")
    print("="*80)
    
    testtool_dir = Path(__file__).resolve().parent.parent
    bin_dir = testtool_dir / "bin"
    smartcheck_bat = bin_dir / "SmiWinTools" / "SmartCheck.bat"
    smart_ini = bin_dir / "SmiWinTools" / "config" / "SMART.ini"
    
    print(f"測試工具目錄: {testtool_dir}")
    print(f"Bin 目錄: {bin_dir}")
    print(f"  - 存在: {bin_dir.exists()}")
    print(f"SmartCheck.bat: {smartcheck_bat}")
    print(f"  - 存在: {smartcheck_bat.exists()}")
    print(f"SMART.ini: {smart_ini}")
    print(f"  - 存在: {smart_ini.exists()}")
    print("="*80 + "\n")
