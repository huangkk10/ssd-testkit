"""
重啟管理器 - 處理系統重啟和狀態恢復
"""
import json
import os
import subprocess
import sys
from pathlib import Path
import getpass
import pytest

class RebootManager:
    """
    管理測試重啟流程
    
    功能：
    - 狀態保存與恢復
    - 開機自啟動設置
    - 測試完成追蹤
    """
    
    STATE_FILE = "./pytest_reboot_state.json"
    STARTUP_PATH = r"C:\Users\{}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\pytest_auto_run.bat"
    
    def __init__(self):
        self.state_file = self.STATE_FILE
        self.state = self._load_state()
    
    def _load_state(self):
        """載入狀態"""
        if Path(self.state_file).exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "completed_tests": [],
            "is_recovering": False,
            "current_test": None,
            "reboot_count": 0
        }
    
    def _save_state(self):
        """保存狀態（強制寫入磁碟）"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    
    def is_recovering(self):
        """檢查是否為重啟後恢復"""
        return self.state.get("is_recovering", False)
    
    def is_completed(self, test_name):
        """檢查測試是否已完成"""
        return test_name in self.state["completed_tests"]
    
    def mark_completed(self, test_name):
        """標記測試完成"""
        if test_name not in self.state["completed_tests"]:
            self.state["completed_tests"].append(test_name)
        self.state["is_recovering"] = False
        self._save_state()
    
    def all_tests_completed(self):
        """檢查所有測試是否完成（用於判斷是否清理）"""
        # 可以根據實際測試數量判斷
        return len(self.state["completed_tests"]) >= 5  # 示例
    
    def setup_reboot(self, delay=10, reason="System reboot required", test_file=None):
        """
        設置重啟流程
        
        Args:
            delay: 重啟延遲時間（秒）
            reason: 重啟原因（用於日誌）
            test_file: 測試文件路徑（用於自動恢復時運行正確的測試）
        """
        # 標記即將重啟
        self.state["is_recovering"] = True
        self.state["reboot_count"] += 1
        self._save_state()
        
        # 設置開機自啟動
        self._setup_auto_start(test_file)
        
        # 顯示訊息
        print(f"\n{'='*60}")
        print(f"[Reboot] {reason}")
        print(f"System will reboot in {delay} seconds...")
        print(f"Tests will resume automatically after reboot.")
        print(f"{'='*60}\n")
        
        # 執行重啟
        try:
            result = subprocess.run(
                ["shutdown", "/r", "/t", str(delay)], 
                capture_output=True, 
                text=True,
                check=True
            )
            print(f"[RebootManager] Reboot command executed successfully")
            if result.stdout:
                print(f"[RebootManager] Output: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"[RebootManager] WARNING: Reboot command failed: {e}")
            print(f"[RebootManager] Error output: {e.stderr}")
            raise
        
        # 强制退出进程，避免任何 cleanup/teardown 代码执行
        # 这样可以确保启动脚本和状态文件不被删除
        print(f"\n[RebootManager] Forcing process exit - system will reboot shortly...")
        print(f"[RebootManager] Startup script and state file preserved for recovery")
        sys.stdout.flush()
        sys.stderr.flush()
        # 使用 os._exit(0) 立即终止进程，不执行任何清理
        os._exit(0)
    
    def _setup_auto_start(self, test_file=None):
        """設置開機自啟動腳本"""
        user = getpass.getuser()
        bat_path = self.STARTUP_PATH.format(user)
        
        # 取得當前執行環境
        python_exe = sys.executable
        current_dir = os.getcwd()
        
        # 如果有指定測試文件，加到命令中
        pytest_args = "-v --tb=short"
        if test_file:
            pytest_args += f" {test_file}"
        
        # 創建啟動腳本
        bat_content = f"""@echo off
cd /d {current_dir}
"{python_exe}" -m pytest {pytest_args}
"""
        
        os.makedirs(os.path.dirname(bat_path), exist_ok=True)
        with open(bat_path, 'w') as f:
            f.write(bat_content)
        
        print(f"[RebootManager] Auto-start script created: {bat_path}")
        if test_file:
            print(f"[RebootManager] Will resume test file: {test_file}")
    
    def cleanup(self):
        """清理狀態和自啟動腳本"""
        # 如果正在恢复中，不清理（因为还在重启流程中）
        if self.state.get("is_recovering", False):
            print("[RebootManager] Skipping cleanup - reboot in progress")
            return
        
        # 刪除狀態文件
        if Path(self.state_file).exists():
            os.remove(self.state_file)
            print("[RebootManager] State file removed")
        
        # 刪除自啟動腳本
        user = getpass.getuser()
        bat_path = self.STARTUP_PATH.format(user)
        if os.path.exists(bat_path):
            os.remove(bat_path)
            print("[RebootManager] Auto-start script removed")
        
        print("[RebootManager] Cleanup completed")
