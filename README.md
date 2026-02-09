# SSD Test Kit

A comprehensive testing framework for SSD (Solid State Drive) validation and quality assurance.

## Project Overview

This repository contains a modular test automation framework designed for SSD testing, including stress testing, SMART monitoring, and disk health validation.

## Repository Structure

```
ssd-testkit/
├── framework/              # Core testing framework
│   ├── base_test.py       # Base test class with reboot support
│   ├── decorators.py      # Test step decorators
│   ├── reboot_manager.py  # Reboot state management
│   ├── system_time_manager.py  # System time control
│   ├── concurrent_runner.py    # Concurrent task runner
│   └── test_utils.py      # Utility functions
├── tests/                 # Test cases
│   └── integration/
│       └── stc1685/       # STC-1685: BurnIN + SmartCheck test
│           ├── test_burnin.py
│           ├── Config/
│           └── bin/
├── lib/                   # Library modules
│   ├── logger.py          # Logging utilities
│   └── testtool/          # Test tool wrappers
│       ├── BurnIN.py      # BurnIN test tool
│       ├── CDI.py         # CrystalDiskInfo wrapper
│       ├── DiskPrd.py     # Disk partition management
│       ├── DiskUtility.py # Disk utilities
│       ├── Diskinfo.py    # Disk information
│       └── SmiSmartCheck.py # SMART monitoring
└── README.md
```

## Features

### Framework Features
- **Reboot Support**: Tests can survive system reboots and continue execution
- **Step Decorators**: Clean test step organization with automatic logging
- **Concurrent Execution**: Run multiple test tools simultaneously
- **SMART Monitoring**: Real-time SSD health monitoring
- **Configurable**: JSON-based configuration for flexible test setup

### Test Cases

#### STC-1685: BurnIN Installation and Stress Test
A comprehensive BurnIN stress test with SMART monitoring:
1. **Precondition**: Remove old installations, clean up logs
2. **Install BurnIN**: Install BurnIN test tool
3. **Partition Disk**: Create test partition (D drive)
4. **CDI Before**: Capture baseline SMART attributes
5. **BurnIN + SmartCheck**: Run concurrent stress test and SMART monitoring
6. **CDI After**: Compare SMART changes and validate no errors

**Test Duration**: Configurable (default: 1440 minutes / 24 hours)

## Requirements

- Python 3.7+
- pytest
- Windows OS (for disk management and tool support)

### Test Tools Required
- BurnIN (bit.exe / bit64.exe)
- CrystalDiskInfo
- SmiSmartCheck

## Installation

1. Clone the repository:
```bash
git clone https://github.com/huangkk10/ssd-testkit.git
cd ssd-testkit
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Configure test settings:
   - Edit test configuration files in `tests/integration/stc1685/Config/Config.json`
   - Place test tool executables in `tests/integration/stc1685/bin/`

## Usage

### Running STC-1685 Test

```bash
cd tests/integration/stc1685
pytest test_burnin.py -v -s
```

### Configuration

Edit `tests/integration/stc1685/Config/Config.json`:

```json
{
  "burnin": {
    "InstallPath": "C:\\Program Files\\BurnIn",
    "test_duration_minutes": 1440,
    "timeout": 6000
  },
  "cdi": {
    "LogPath": "./testlog"
  },
  "smartcheck": {
    "monitoring_interval": 60
  }
}
```

## Test Output

Test results are saved to:
- `testlog/`: Tool outputs (CDI reports, BurnIN logs, screenshots)
- `log/STC-1685/`: Test execution logs

## Framework API

### BaseTestCase
Base class for all tests with reboot support:
```python
from framework.base_test import BaseTestCase

class MyTest(BaseTestCase):
    def test_example(self):
        # Your test code
        pass
```

### Step Decorator
Organize test steps with automatic logging:
```python
from framework.decorators import step

@step(1, "Setup precondition")
def test_01_precondition(self):
    # Test step code
    pass
```

## Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

[Specify your license here]

## Contact

For questions or support, please contact the repository maintainer.

## Changelog

### Initial Release
- Framework migration from main automation project
- STC-1685 BurnIN test case
- Core lib utilities for disk testing
