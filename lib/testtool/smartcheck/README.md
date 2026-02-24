# SmartCheck Controller

Threading-based controller for managing SmartCheck.bat execution and monitoring.

## 📁 文件结构

```
ssd-testkit/
└── lib/
    └── testtool/
        └── smartcheck/
            ├── __init__.py           # Package initialization
            ├── controller.py         # Main SmartCheckController class
            ├── config.py             # Configuration management
            ├── exceptions.py         # Custom exceptions
            ├── example_usage.py      # Usage examples
            └── README.md             # This file
```

## 🚀 快速开始

### 基本使用

```python
from lib.testtool.smartcheck import SmartCheckController

# Create controller
controller = SmartCheckController(
    bat_path="./bin/SmiWinTools/SmartCheck.bat",
    cfg_ini_path="./bin/SmiWinTools/SmartCheck.ini",
    output_dir="./test_output"
)

# Configure parameters
controller.set_config(
    total_time=60,       # Run for 60 minutes
    dut_id="0",          # Device ID
    timeout=180          # 3 minute timeout
)

# Start the thread
controller.start()

# Wait for completion
controller.join(timeout=200)

# Check result
if controller.status:
    print("SmartCheck passed!")
else:
    print("SmartCheck failed!")
```

## 📋 功能特性

### ✅ 已实现功能

1. **配置管理**
   - 支持 8 个 SmartCheck.ini 参数
   - JSON 配置文件加载
   - 动态参数设置
   - 参数验证

2. **进程控制**
   - 启动 SmartCheck.bat
   - 优雅停止 / 强制终止
   - 进程状态监控

3. **状态监控**
   - RunCard.ini 自动查找
   - 状态读取和解析
   - 错误检测（大小写不敏感）

4. **线程支持**
   - 完全 threading.Thread 实现
   - 支持并发运行多个实例
   - 线程安全的停止机制

5. **错误处理**
   - 完善的异常体系
   - 超时机制
   - 详细的日志记录

## 🔧 配置参数

### 必要参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_dir` | str | - | 输出目录（绝对路径） |
| `total_cycle` | int | 0 | 总循环次数（0=无限） |
| `total_time` | int | 10080 | 总时间（分钟，默认7天） |
| `dut_id` | str | "" | Device Under Test ID |
| `enable_monitor_smart` | bool | True | 启用 SMART 监控 |
| `close_window_when_failed` | bool | False | 失败时关闭窗口 |
| `stop_when_failed` | bool | True | 失败时停止 |
| `smart_config_file` | str | "config\\SMART.ini" | SMART 配置文件路径 |

### 控制参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout` | int | 3600 | 超时时间（秒） |
| `check_interval` | int | 3 | 状态检查间隔（秒） |

## 📖 使用示例

### 示例 1: 基本使用

```python
controller = SmartCheckController(
    bat_path="./bin/SmiWinTools/SmartCheck.bat",
    cfg_ini_path="./bin/SmiWinTools/SmartCheck.ini",
    output_dir="./test_output"
)

controller.set_config(total_time=60, dut_id="0")
controller.start()
controller.join(timeout=200)

print(f"Status: {controller.status}")
```

### 示例 2: 使用 JSON 配置

```python
# config.json
{
    "smartcheck": {
        "total_time": 60,
        "dut_id": "0",
        "timeout": 180
    }
}

# Python code
controller = SmartCheckController(bat_path, cfg_path, output_dir)
controller.load_config_from_json("config.json")
controller.start()
```

### 示例 3: 实时监控

```python
controller.start()

while controller.is_alive():
    print(f"Running... Status: {controller.status}")
    time.sleep(5)

print(f"Final status: {controller.status}")
```

### 示例 4: 提前停止

```python
controller.start()

# Run for 30 seconds then stop
time.sleep(30)
controller.stop()
controller.join(timeout=10)
```

### 示例 5: 并发运行

```python
# Create multiple controllers
controllers = []
for i in range(3):
    ctrl = SmartCheckController(
        bat_path=bat_path,
        cfg_ini_path=cfg_path,
        output_dir=f"./output_{i}"
    )
    ctrl.set_config(dut_id=str(i))
    controllers.append(ctrl)

# Start all
for ctrl in controllers:
    ctrl.start()

# Wait for all
for ctrl in controllers:
    ctrl.join()

# Check results
all_passed = all(ctrl.status for ctrl in controllers)
```

## 🧪 测试

### 运行单元测试

```bash
cd ssd-testkit
pytest tests/unit/lib/testtool/test_smartcheck/test_controller.py -v
```

### 运行示例

```bash
cd ssd-testkit/lib/testtool/smartcheck
python example_usage.py
```

## 📝 API 文档

### SmartCheckController

主控制器类，继承自 `threading.Thread`。

#### 方法

##### `__init__(bat_path, cfg_ini_path, output_dir, **kwargs)`
初始化控制器。

##### `set_config(**kwargs)`
设置配置参数。

##### `load_config_from_json(json_path)`
从 JSON 文件加载配置。

##### `update_smartcheck_ini(section, key, value)`
更新 SmartCheck.ini 特定键值。

##### `write_all_config_to_ini()`
将所有配置写入 SmartCheck.ini。

##### `clear_output_dir()`
清空输出目录。

##### `ensure_output_dir_exists()`
确保输出目录存在。

##### `start_smartcheck_bat()`
启动 SmartCheck.bat 进程。

##### `stop_smartcheck_bat(force=False)`
停止 SmartCheck.bat 进程。

##### `find_runcard_ini()`
在输出目录中查找 RunCard.ini。

##### `read_runcard_status(runcard_path)`
读取 RunCard.ini 状态信息。

##### `check_runcard_status(status_dict)`
检查 RunCard 状态是否正常。

##### `run()`
线程主函数（通过 `start()` 调用）。

##### `stop()`
请求线程停止执行。

## ⚠️ 注意事项

### RunCard.ini 状态值

- **test_result**: `ONGOING` / `PASSED` / `FAILED` (大写)
- **err_msg**: 
  - `"No Error"` 或 `"pass"` → 正常
  - 其他任何值 → 错误

### SmartCheck.bat 初始化时间

SmartCheck.bat 启动需要约 **2-3 分钟**初始化时间，请确保 `timeout` 参数足够大（建议 > 180 秒）。

### output_dir 配置

⚠️ **重要**: SmartCheck.bat 可能**忽略** `output_dir` 配置，始终输出到 `bin/SmiWinTools/log_SmartCheck/YYYYMMDDHHMMSS/`。

控制器会在指定的 `output_dir` 中递归搜索 RunCard.ini。

### 线程安全

- 每个 `SmartCheckController` 实例运行在独立线程中
- 使用不同的 `output_dir` 避免文件冲突
- 使用 `stop()` 方法优雅停止线程

## 🆚 对比旧版本

| 特性 | 旧版本 (SmiSmartCheck.py) | 新版本 (SmartCheckController) |
|------|---------------------------|-------------------------------|
| 并发模型 | async/await + threading | 纯 threading |
| 路径处理 | 复杂的路径计算（有bug） | 直接递归搜索 |
| 状态检查 | 大小写敏感（有bug） | 大小写不敏感 |
| 配置管理 | 分散的方法 | 统一的配置类 |
| 错误处理 | 基础 | 完善的异常体系 |
| 代码结构 | 单文件 600+ 行 | 模块化，易维护 |
| 测试性 | 难以测试 | 易于单元测试 |
| 文档 | 缺少 | 完整的文档和示例 |

## 🐛 已知问题

1. **SmartCheck.bat output_dir 配置可能被忽略**
   - 缓解: 控制器递归搜索整个 output_dir

2. **Windows 进程终止可能失败**
   - 缓解: 多层终止策略（terminate → kill → taskkill）

## 🔄 版本历史

### v1.0.0 (2026-02-10)
- ✅ 初始版本发布
- ✅ 完整的 threading 支持
- ✅ 配置管理
- ✅ 进程控制
- ✅ RunCard 监控
- ✅ 单元测试
- ✅ 使用示例

## 📞 技术支持

如有问题或建议，请查看：
- 计划文档: `SmartCheck_Controller_Plan.md`
- 单元测试: `tests/unit/lib/testtool/test_smartcheck/`
- 使用示例: `example_usage.py`

---

**Created**: 2026-02-10  
**Version**: 1.0.0  
**Status**: ✅ Production Ready
