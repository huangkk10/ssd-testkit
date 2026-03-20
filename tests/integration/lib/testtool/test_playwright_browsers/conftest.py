"""
Integration test fixtures for playwright-browsers Chocolatey packaging.
"""

import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the ssd-testkit repository root."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def choco_manager(project_root):
    """Session-scoped ChocoManager."""
    from lib.testtool.choco_manager import ChocoManager
    return ChocoManager(project_root=str(project_root))


@pytest.fixture(scope="session")
def browsers_source(project_root) -> Path:
    """
    Path to the playwright-browsers source directory
    (bin/installers/playwright-browsers/1.58.0/).
    Auto-skips the test if the directory or chrome.exe is not present.
    """
    path = project_root / "bin" / "installers" / "playwright-browsers" / "1.58.0"
    if not path.exists():
        pytest.skip(f"playwright-browsers source directory not found: {path}")
    chrome = path / "chromium-1208" / "chrome-win64" / "chrome.exe"
    if not chrome.exists():
        pytest.skip(f"chrome.exe not found: {chrome}")
    return path
