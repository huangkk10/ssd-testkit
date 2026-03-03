"""
Root conftest.py — project-wide pytest hooks.

Hardware / real-device tests are skipped by default.
To run them, pass --run-hardware on the command line:

    pytest --run-hardware -m real_bat tests/unit/lib/testtool/test_smartcheck/
"""

import pytest

_HARDWARE_MARKS = {"real_bat", "real", "hardware"}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="Include tests marked real_bat / real / hardware (requires physical device).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-hardware"):
        return  # opt-in: run everything as requested

    skip = pytest.mark.skip(
        reason="Skipped by default (requires physical hardware). "
               "Pass --run-hardware to execute."
    )
    for item in items:
        item_marks = {m.name for m in item.iter_markers()}
        if item_marks & _HARDWARE_MARKS:
            item.add_marker(skip)
