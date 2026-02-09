"""
基礎測試類，所有測試案例繼承此類
提供標準的 setup/teardown 和狀態管理
"""
import pytest
import shutil
from pathlib import Path
from framework.reboot_manager import RebootManager
from framework.test_utils import setup_test_environment, cleanup_test_environment
import lib.logger as logger

class BaseTestCase:
    """
    測試基礎類
    
    使用方式：
        class TestYourCase(BaseTestCase):
            def test_step_01(self):
                # 測試邏輯
                pass
    """
    
    # ========== Class-level Setup/Teardown ==========
    @pytest.fixture(scope="class", autouse=True)
    def setup_teardown_class(self, request):
        """類別層級的 setup 和 teardown"""
        # Setup：初始化測試環境
        cls = request.cls
        cls.test_name = request.node.name
        cls.log_path = "./testlog"
        cls.reboot_mgr = RebootManager()
        
        # 只在首次執行時初始化（重啟後跳過）
        if not cls.reboot_mgr.is_recovering():
            logger.LogEvt("=" * 60)
            logger.LogEvt(f"Setting up test: {cls.test_name}")
            logger.LogEvt("=" * 60)
            setup_test_environment(cls.log_path)
        else:
            logger.LogEvt("=" * 60)
            logger.LogEvt(f"Recovering test: {cls.test_name}")
            logger.LogEvt("=" * 60)
        
        yield  # 測試執行
        
        # Teardown：清理測試環境
        if cls.reboot_mgr.all_tests_completed():
            logger.LogEvt("=" * 60)
            logger.LogEvt("All tests completed, cleaning up...")
            logger.LogEvt("=" * 60)
            cleanup_test_environment()
            cls.reboot_mgr.cleanup()
    
    # ========== Function-level Setup/Teardown ==========
    @pytest.fixture(autouse=True)
    def setup_teardown_function(self, request):
        """函數層級的 setup 和 teardown"""
        test_name = request.node.name
        
        # Setup：檢查是否應該跳過
        if self.reboot_mgr.is_completed(test_name):
            pytest.skip(f"{test_name} already completed")
        
        logger.LogEvt(f"--- Starting: {test_name} ---")
        
        yield  # 測試執行
        
        # Teardown：標記完成
        logger.LogEvt(f"--- Completed: {test_name} ---")
        self.reboot_mgr.mark_completed(test_name)
    
    # ========== 輔助方法 ==========
    def get_config(self, key, default=None):
        """讀取配置"""
        import json
        try:
            with open("./Config/Config.json", 'r') as f:
                config = json.load(f)
                return config.get(key, default)
        except:
            return default
    
    def log(self, message):
        """統一的日誌輸出"""
        logger.LogEvt(f"[LOG] {message}")
    
    def log_info(self, message):
        """記錄資訊訊息"""
        logger.LogEvt(f"[INFO] {message}")
    
    def log_error(self, message):
        """記錄錯誤訊息"""
        logger.LogErr(f"[ERROR] {message}")
    
    def log_step(self, step_number, description):
        """記錄測試步驟"""
        logger.LogEvt("=" * 60)
        logger.LogEvt(f"[STEP {step_number}] {description}")
        logger.LogEvt("=" * 60)
    
    def log_result(self, passed, message):
        """記錄測試結果"""
        if passed:
            logger.LogEvt(f"✓ [PASS] {message}")
        else:
            logger.LogErr(f"✗ [FAIL] {message}")
    
    def log_section(self, title):
        """記錄測試區段"""
        logger.LogEvt("")
        logger.LogEvt("=" * 60)
        logger.LogEvt(f"  {title}")
        logger.LogEvt("=" * 60)
        logger.LogEvt("")
