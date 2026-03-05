"""
Shared fixtures for test_sleepstudy unit tests.
"""
import json
import pytest
from pathlib import Path

from lib.testtool.sleepstudy.sleep_report_parser import _TICKS_PER_SECOND, SESSION_TYPE_SLEEP


# ---------------------------------------------------------------------------
# HTML / JSON builders (shared with test_sleep_report_parser.py)
# ---------------------------------------------------------------------------

def make_sleep_scenario(
    session_id: int = 6,
    entry_local: str = "2026-03-04T11:06:34",
    exit_local: str = "2026-03-04T11:21:46",
    duration_seconds: float = 912.4,
    sw_pct: int = 98,
    hw_pct: int = 98,
    on_ac: bool = True,
) -> dict:
    dur_ticks = int(duration_seconds * _TICKS_PER_SECOND)
    sw_ticks = int(sw_pct * dur_ticks * 10 / 100)
    hw_ticks = int(hw_pct * dur_ticks * 10 / 100)
    return {
        "Type": SESSION_TYPE_SLEEP,
        "SessionId": session_id,
        "EntryTimestampLocal": entry_local,
        "ExitTimestampLocal": exit_local,
        "Duration": dur_ticks,
        "OnAc": on_ac,
        "BatteryCountChanged": False,
        "Metadata": {
            "FriendlyName": "Detailed Session Information",
            "Values": [
                {"Key": "Info.SwLowPowerStateTime", "Value": sw_ticks},
                {"Key": "Info.HwLowPowerStateTime", "Value": hw_ticks},
            ],
        },
    }


def make_spr_data(scenarios: list) -> dict:
    return {
        "ReportInformation": {"ReportVersion": "1.1"},
        "SystemInformation": {},
        "Batteries": [],
        "EnergyDrains": [],
        "ScenarioInstances": scenarios,
    }


def make_html_with_data(spr_data: dict) -> str:
    json_str = json.dumps(spr_data)
    return f"""<!DOCTYPE html>
<html lang="en">
<head><title>System Power Report</title></head>
<body>
<script>
    var LocalSprData = {json_str};
</script>
</body>
</html>
"""


@pytest.fixture
def sample_html_file(tmp_path) -> str:
    """A minimal valid sleepstudy HTML file with one Sleep session."""
    html = make_html_with_data(make_spr_data([
        make_sleep_scenario(session_id=6, entry_local="2026-03-04T11:06:34"),
    ]))
    p = tmp_path / "sleepstudy-report.html"
    p.write_text(html, encoding="utf-8")
    return str(p)


@pytest.fixture
def sample_config() -> dict:
    return {
        "output_path": "sleepstudy-report.html",
        "timeout": 60,
    }
