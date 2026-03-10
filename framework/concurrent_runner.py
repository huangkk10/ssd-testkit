"""
Concurrent runner - uses threads to execute tasks concurrently
"""
import threading
import queue
import time
from typing import Callable, List, Tuple, Any

class ConcurrentRunner:
    """
    Concurrent runner (thread-based)

    Usage:
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
        Run multiple tasks concurrently

        Args:
            tasks: [(function, args_tuple, task_name), ...]
            timeout: timeout in seconds, None means no limit
            return_when: "FIRST_COMPLETED" or "ALL_COMPLETED"

        Returns:
            {"success": bool, "completed": task name or list, "result": result, "error": error message}
        """
        threads = []
        
        # Start all tasks
        for func, args, task_name in tasks:
            thread = threading.Thread(
                target=self._run_task,
                args=(func, args, task_name),
                daemon=True
            )
            thread.start()
            threads.append((thread, task_name))
        
        # Wait for tasks to complete
        start_time = time.time()
        completed_tasks = []
        
        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                self.stop_event.set()
                return {
                    "success": False,
                    "completed": None,
                    "result": None,
                    "error": f"Timeout after {timeout} seconds"
                }
            
            # Check result queue
            try:
                task_name, success, result = self.result_queue.get(timeout=0.5)
                completed_tasks.append((task_name, success, result))
                
                # FIRST_COMPLETED: return upon first task completion
                if return_when == "FIRST_COMPLETED":
                    self.stop_event.set()
                    return {
                        "success": success,
                        "completed": task_name,
                        "result": result,
                        "error": None if success else result
                    }
                
                # ALL_COMPLETED: check if all tasks finished
                if return_when == "ALL_COMPLETED" and len(completed_tasks) == len(tasks):
                    return {
                        "success": all([r[1] for r in completed_tasks]),
                        "completed": [r[0] for r in completed_tasks],
                        "result": completed_tasks,
                        "error": None
                    }
                
            except queue.Empty:
                # Check whether all threads have finished
                if return_when == "ALL_COMPLETED":
                    if not any(t.is_alive() for t, _ in threads):
                        break
                continue
        
        # Wait for all threads to finish
        for thread, _ in threads:
            thread.join(timeout=1)
        
        return {
            "success": len(completed_tasks) > 0,
            "completed": [r[0] for r in completed_tasks],
            "result": completed_tasks,
            "error": None
        }
    
    def _run_task(self, func: Callable, args: tuple, task_name: str):
        """Execute a single task"""
        try:
            result = func(*args)
            if not self.stop_event.is_set():
                self.result_queue.put((task_name, True, result))
        except Exception as e:
            if not self.stop_event.is_set():
                self.result_queue.put((task_name, False, str(e)))
    
    def reset(self):
        """Reset state"""
        self.stop_event.clear()
        # Clear queue
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break


# ========== Helper functions ==========
def run_with_monitoring(main_task, monitor_task, timeout=None):
    """
    Run a main task while monitoring it with a secondary task

    Args:
        main_task: (function, args, name)
        monitor_task: (function, args, name)
        timeout: timeout in seconds

    Returns:
        execution result
    """
    runner = ConcurrentRunner()
    result = runner.run_concurrent(
        tasks=[main_task, monitor_task],
        timeout=timeout,
        return_when="FIRST_COMPLETED"
    )
    return result
