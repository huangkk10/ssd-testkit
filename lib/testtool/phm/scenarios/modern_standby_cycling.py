"""
Modern Standby Cycling — Scenario Parameters

Represents the configurable fields inside the **Modern Standby Cycling**
preset scenario in the PHM Collector tab:

    Delayed Start (seconds)
    Scenario Duration (minutes)
    Cycle Count

Usage::

    from lib.testtool.phm.scenarios.modern_standby_cycling import (
        ModernStandbyCyclingParams,
    )

    params = ModernStandbyCyclingParams(
        delayed_start_seconds=10,
        scenario_duration_minutes=2,
        cycle_count=5,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import ScenarioParams


@dataclass
class ModernStandbyCyclingParams(ScenarioParams):
    """
    Parameters for the *Modern Standby Cycling* preset scenario.

    Attributes:
        delayed_start_seconds:      Seconds to wait before the first cycle
                                    begins (``Delayed Start`` field).
        scenario_duration_minutes:  Duration of each cycle in minutes
                                    (``Scenario Duration`` field).
        cycle_count:                Total number of standby/wake cycles
                                    (``Cycle Count`` field).
    """

    delayed_start_seconds: int = field(default=10)
    scenario_duration_minutes: int = field(default=1)
    cycle_count: int = field(default=10)

    # ------------------------------------------------------------------
    # Validation (called automatically in __post_init__)
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if self.delayed_start_seconds < 0:
            raise ValueError(
                f"delayed_start_seconds must be >= 0, got {self.delayed_start_seconds}"
            )
        if self.scenario_duration_minutes < 1:
            raise ValueError(
                f"scenario_duration_minutes must be >= 1, got {self.scenario_duration_minutes}"
            )
        if self.cycle_count < 1:
            raise ValueError(
                f"cycle_count must be >= 1, got {self.cycle_count}"
            )

    # ------------------------------------------------------------------
    # ScenarioParams interface
    # ------------------------------------------------------------------

    @property
    def scenario_name(self) -> str:
        """radio button label in the PHM Collector UI."""
        return "Modern Standby Cycling"
