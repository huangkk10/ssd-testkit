"""
通用測試工具函數
"""
import shutil
from pathlib import Path
import subprocess
import time

# ========== 環境管理 ==========
def setup_test_environment(log_path: str):
    """初始化測試環境"""
    # 清理舊日誌
    if Path(log_path).exists():
        shutil.rmtree(log_path)
    
    # 創建日誌目錄
    Path(log_path).mkdir(parents=True, exist_ok=True)
    print(f"[TestUtils] Test environment initialized: {log_path}")

def cleanup_test_environment():
    """清理測試環境"""
    print("[TestUtils] Test environment cleaned up")

# ========== 重啟相關 ==========
def need_reboot() -> bool:
    """判斷是否需要重啟（示例實現）"""
    # 可根據實際需求實現判斷邏輯
    return False

def reboot_system(delay: int = 10, reason: str = "Test requires reboot", test_file: str = None):
    """
    重啟系統的便利函數
    
    使用方式：
        from framework.test_utils import reboot_system
        reboot_system(delay=10, reason="After S3/S4 test", test_file=__file__)
    
    Args:
        delay: 重啟延遲時間（秒）
        reason: 重啟原因
        test_file: 當前測試文件路徑（用於重啟後恢復）
    """
    from framework.reboot_manager import RebootManager
    
    print(f"\n[Reboot] {reason}")
    mgr = RebootManager()
    mgr.setup_reboot(delay=delay, reason=reason, test_file=test_file)

# ========== 工具執行 ==========
def run_tool_with_retry(tool_func, max_retry: int = 3, retry_delay: int = 5):
    """
    帶重試機制的工具執行
    
    Args:
        tool_func: 工具函數
        max_retry: 最大重試次數
        retry_delay: 重試延遲（秒）
    
    Returns:
        執行結果
    """
    for attempt in range(max_retry):
        try:
            result = tool_func()
            return result
        except Exception as e:
            print(f"[Retry] Attempt {attempt + 1} failed: {e}")
            if attempt < max_retry - 1:
                time.sleep(retry_delay)
            else:
                raise

# ========== 文件操作 ==========
def ensure_file_exists(file_path: str, timeout: int = 30) -> bool:
    """
    等待文件生成
    
    Args:
        file_path: 文件路徑
        timeout: 超時時間（秒）
    
    Returns:
        文件是否存在
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if Path(file_path).exists():
            return True
        time.sleep(1)
    return False
