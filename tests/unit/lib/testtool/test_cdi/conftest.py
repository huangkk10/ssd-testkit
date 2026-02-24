"""
Pytest configuration and fixtures for CDI unit tests.
"""

import json
import os
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_log_path(temp_dir):
    """Temporary log file path (not created yet)."""
    return os.path.join(temp_dir, 'DiskInfo.txt')


@pytest.fixture
def sample_config():
    """Minimal valid configuration dictionary."""
    return {
        'executable_path': './bin/CrystalDiskInfo/DiskInfo64.exe',
        'log_path': './testlog',
        'timeout_seconds': 60,
    }


@pytest.fixture
def sample_diskinfo_json(temp_dir):
    """Write a minimal DiskInfo.json and return its path."""
    data = {
        'disks': [
            {
                'DiskNum': '1',
                'Model': 'Samsung SSD 980 PRO',
                'Drive Letter': 'C:',
                'S.M.A.R.T.': [
                    {'ID': '01', 'RawValues': '000000000005', 'Attribute Name': 'Power Cycles'},
                    {'ID': '09', 'RawValues': '0000000000FF', 'Attribute Name': 'Power On Hours'},
                    {'ID': 'AE', 'RawValues': '000000000000', 'Attribute Name': 'Unsafe Shutdowns'},
                ],
            }
        ]
    }
    path = os.path.join(temp_dir, 'DiskInfo.json')
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


@pytest.fixture
def sample_diskinfo_txt(temp_dir):
    """Write a minimal DiskInfo.txt and return its path."""
    content = (
        'CrystalDiskInfo 9.0.0 (C) 2008-2024 hiyohiyo\n'
        '    OS : Windows 11 Pro\n'
        '-- Controller Map\n'
        ' + Standard NVM Express Controller\n'
        '   - Samsung SSD 980 PRO\n'
        '-- Disk List\n'
        ' (1) Samsung SSD 980 PRO : 1000.2 GB [0/0/0, pd1]\n'
        '-----------------\n'
        ' (1) Samsung SSD 980 PRO\n'
        ' Model : Samsung SSD 980 PRO\n'
        ' Drive Letter : C:\n'
        '-- S.M.A.R.T. Samsung SSD 980 PRO\n'
        '01 000000000005 Power Cycles\n'
    )
    path = os.path.join(temp_dir, 'DiskInfo.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path
