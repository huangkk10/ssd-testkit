"""
Integration test fixtures for test_sleepstudy.
"""
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def workspace_root() -> Path:
    """Return the ssd-testkit workspace root directory."""
    # tests/integration/lib/testtool/test_sleepstudy/ -> 5 levels up
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def real_html_path(workspace_root) -> str:
    """
    Path to ``tmp/sleepstudy-report.html``.
    Skip the whole session if the file does not exist.
    """
    path = workspace_root / "tmp" / "sleepstudy-report.html"
    if not path.exists():
        pytest.skip(f"Sleep study HTML not found: {path}")
    return str(path)
