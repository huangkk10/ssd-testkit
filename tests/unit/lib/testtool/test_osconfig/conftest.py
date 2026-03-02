"""
Pytest configuration and shared fixtures for OsConfig unit tests.
"""

import pytest
from unittest.mock import patch, MagicMock

from lib.testtool.osconfig.os_compat import WindowsBuildInfo


@pytest.fixture
def win10_build():
    """WindowsBuildInfo for a typical Windows 10 22H2 Pro machine."""
    return WindowsBuildInfo(
        major=10, build=19045, edition="Pro",
        version_tag="win10", product_name="Windows 10 Pro",
    )


@pytest.fixture
def win11_build():
    """WindowsBuildInfo for a typical Windows 11 22H2 Pro machine."""
    return WindowsBuildInfo(
        major=10, build=22621, edition="Pro",
        version_tag="win11", product_name="Windows 11 Pro",
    )


@pytest.fixture
def win10_home_build():
    """WindowsBuildInfo for Windows 10 Home (old RS0, pre-RS1)."""
    return WindowsBuildInfo(
        major=10, build=10586, edition="Home",
        version_tag="win10", product_name="Windows 10 Home",
    )


@pytest.fixture
def win_server_build():
    """WindowsBuildInfo for Windows Server 2022."""
    return WindowsBuildInfo(
        major=10, build=20348, edition="Server",
        version_tag="win10", product_name="Windows Server 2022 Datacenter",
    )


@pytest.fixture
def win10_pre_tamper_build():
    """WindowsBuildInfo for Windows 10 1809 (Build 17763) – pre Tamper Protection."""
    return WindowsBuildInfo(
        major=10, build=17763, edition="Pro",
        version_tag="win10", product_name="Windows 10 Pro",
    )


@pytest.fixture
def win10_post_tamper_build():
    """WindowsBuildInfo for Windows 10 1903 (Build 18362) – Tamper Protection era."""
    return WindowsBuildInfo(
        major=10, build=18362, edition="Pro",
        version_tag="win10", product_name="Windows 10 Pro",
    )


@pytest.fixture
def mock_snapshot_store():
    """Empty dict to use as a shared snapshot store in action tests."""
    return {}
