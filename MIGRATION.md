# 项目迁移说明

## 迁移内容

本次迁移已成功将以下内容从主项目迁移到新的 `ssd-testkit` repository：

### 1. Framework 框架 ✅
完整迁移了 `framework/` 目录，包含：
- `base_test.py` - 基础测试类（支持重启）
- `decorators.py` - 测试步骤装饰器
- `reboot_manager.py` - 重启状态管理
- `system_time_manager.py` - 系统时间控制
- `concurrent_runner.py` - 并发任务执行
- `test_utils.py` - 工具函数

### 2. STC-1685 测试项目 ✅
完整迁移了 `tests/integration/stc1685/`，包含：
- `test_burnin.py` - 主测试文件
- `Config/` - 配置文件目录
- `bin/` - 测试工具二进制文件
- 相关文档（README.md, CHANGES.md, SETUP_COMPLETE.md）

### 3. 依赖的 Lib 模块 ✅
仅迁移 `test_burnin.py` 实际使用的模块：

#### lib/
- `logger.py` - 日志模块

#### lib/testtool/
- `BurnIN.py` - BurnIN 测试工具封装
- `CDI.py` - CrystalDiskInfo 封装
- `DiskPrd.py` - 磁盘分区管理
- `DiskUtility.py` - 磁盘工具（DiskPrd 依赖）
- `Diskinfo.py` - 磁盘信息（DiskUtility 依赖）
- `SmiSmartCheck.py` - SMART 监控工具

### 4. 项目文档 ✅
- `README.md` - 项目说明文档
- `.gitignore` - Git 忽略规则
- `requirements.txt` - Python 依赖包列表

## 目录结构

```
ssd-testkit/
├── .gitignore              # Git 忽略规则
├── README.md               # 项目说明
├── requirements.txt        # Python 依赖
├── framework/              # 测试框架
│   ├── __init__.py
│   ├── base_test.py
│   ├── concurrent_runner.py
│   ├── decorators.py
│   ├── reboot_manager.py
│   ├── system_time_manager.py
│   └── test_utils.py
├── lib/                    # 库模块
│   ├── __init__.py
│   ├── logger.py
│   └── testtool/
│       ├── __init__.py
│       ├── BurnIN.py
│       ├── CDI.py
│       ├── DiskPrd.py
│       ├── DiskUtility.py
│       ├── Diskinfo.py
│       └── SmiSmartCheck.py
└── tests/                  # 测试用例
    ├── __init__.py
    └── integration/
        ├── __init__.py
        └── stc1685/
            ├── __init__.py
            ├── test_burnin.py
            ├── Config/
            ├── bin/
            └── README.md
```

## 下一步操作

### 1. 初始化 Git Repository

```bash
cd c:\automation\ssd-testkit
git init
git add .
git commit -m "Initial commit: Migrate framework and STC-1685 test"
```

### 2. 连接到 GitHub

```bash
git remote add origin https://github.com/huangkk10/ssd-testkit.git
git branch -M main
git push -u origin main
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 测试运行

```bash
cd tests/integration/stc1685
pytest test_burnin.py -v -s
```

## 依赖关系图

```
test_burnin.py
├── framework.base_test
├── framework.decorators
├── lib.logger
└── lib.testtool
    ├── BurnIN
    │   └── lib.logger
    ├── CDI
    │   └── lib.logger
    ├── DiskPrd
    │   ├── lib.logger
    │   └── lib.testtool.DiskUtility
    │       ├── lib.logger
    │       └── lib.testtool.Diskinfo
    └── SmiSmartCheck
        └── lib.logger
```

## 迁移说明

1. **排除的文件**：
   - `__pycache__/` 目录
   - 日志文件 (`*.log`)
   - 测试输出 (`testlog/`, `log/`)
   - 临时文件 (`*.json`, `*.png`, `*.pdf`)

2. **包含的文件**：
   - 所有 `.py` 源代码
   - 配置文件 (`Config.json`, `*.bitcfg`)
   - 文档文件 (`.md`)
   - 工具依赖 (`bin/` 目录)

3. **已添加 `__init__.py`**：
   - `lib/__init__.py`
   - `lib/testtool/__init__.py`
   - `tests/__init__.py`
   - `tests/integration/__init__.py`
   - `tests/integration/stc1685/__init__.py`

## 注意事项

1. **测试工具二进制文件**：
   - BurnIN、CDI、SmiSmartCheck 等工具需要手动放置到 `tests/integration/stc1685/bin/` 目录
   - 或者修改 `Config/Config.json` 中的路径配置

2. **配置文件**：
   - 检查 `tests/integration/stc1685/Config/Config.json` 中的路径设置
   - 根据实际环境调整工具路径和测试参数

3. **Python 环境**：
   - 建议使用 Python 3.7 或更高版本
   - 安装所有依赖包：`pip install -r requirements.txt`

## 联系方式

如有问题，请联系项目维护者。
