"""
並發執行器 - 使用 Thread 實現並發任務執行
"""
import threading
import queue
import time
from typing import Callable, List, Tuple, Any

class ConcurrentRunner:
    """
    並發執行器（基於 Thread）
    
    使用方式：
        runner = ConcurrentRunner()
        result = runner.run_concurrent([task1, task2], timeout=300)
    """
    
    def __init__(self):
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
    
    def run_concurrent(
        self, 
        tasks: List[Tuple[Callable, tuple, str]], 
        timeout: int = None,
        return_when: str = "FIRST_COMPLETED"
    ) -> dict:
        """
        並發執行多個任務
        
        Args:
            tasks: [(函數, 參數tuple, 任務名稱), ...]
            timeout: 超時時間（秒），None 表示不限制
            return_when: "FIRST_COMPLETED" 或 "ALL_COMPLETED"
        
        Returns:
            {"success": bool, "completed": 任務名稱, "result": 結果, "error": 錯誤訊息}
        """
        threads = []
        
        # 啟動所有任務
        for func, args, task_name in tasks:
            thread = threading.Thread(
                target=self._run_task,
                args=(func, args, task_name),
                daemon=True
            )
            thread.start()
            threads.append((thread, task_name))
        
        # 等待任務完成
        start_time = time.time()
        completed_tasks = []
        
        while True:
            # 檢查超時
            if timeout and (time.time() - start_time) > timeout:
                self.stop_event.set()
                return {
                    "success": False,
                    "completed": None,
                    "result": None,
                    "error": f"Timeout after {timeout} seconds"
                }
            
            # 檢查結果隊列
            try:
                task_name, success, result = self.result_queue.get(timeout=0.5)
                completed_tasks.append((task_name, success, result))
                
                # FIRST_COMPLETED：有任務完成就返回
                if return_when == "FIRST_COMPLETED":
                    self.stop_event.set()
                    return {
                        "success": success,
                        "completed": task_name,
                        "result": result,
                        "error": None if success else result
                    }
                
                # ALL_COMPLETED：檢查是否所有任務都完成
                if return_when == "ALL_COMPLETED" and len(completed_tasks) == len(tasks):
                    return {
                        "success": all([r[1] for r in completed_tasks]),
                        "completed": [r[0] for r in completed_tasks],
                        "result": completed_tasks,
                        "error": None
                    }
                
            except queue.Empty:
                # 檢查是否所有線程都結束
                if return_when == "ALL_COMPLETED":
                    if not any(t.is_alive() for t, _ in threads):
                        break
                continue
        
        # 等待所有線程結束
        for thread, _ in threads:
            thread.join(timeout=1)
        
        return {
            "success": len(completed_tasks) > 0,
            "completed": [r[0] for r in completed_tasks],
            "result": completed_tasks,
            "error": None
        }
    
    def _run_task(self, func: Callable, args: tuple, task_name: str):
        """執行單個任務"""
        try:
            result = func(*args)
            if not self.stop_event.is_set():
                self.result_queue.put((task_name, True, result))
        except Exception as e:
            if not self.stop_event.is_set():
                self.result_queue.put((task_name, False, str(e)))
    
    def reset(self):
        """重置狀態"""
        self.stop_event.clear()
        # 清空隊列
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break


# ========== 便利函數 ==========
def run_with_monitoring(main_task, monitor_task, timeout=None):
    """
    執行主任務並同時監控
    
    Args:
        main_task: (函數, 參數, 名稱)
        monitor_task: (函數, 參數, 名稱)
        timeout: 超時時間
    
    Returns:
        執行結果
    """
    runner = ConcurrentRunner()
    result = runner.run_concurrent(
        tasks=[main_task, monitor_task],
        timeout=timeout,
        return_when="FIRST_COMPLETED"
    )
    return result
