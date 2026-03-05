"""
PHM Collector — Scenario Parameter Base Class

Each Preset Scenario in the PHM Collector tab is represented as a
:class:`ScenarioParams` subclass (a dataclass).  The subclass declares
only the fields that appear in its section of the UI and implements
:attr:`scenario_name` to return the exact label shown next to the
radio button.

Design rationale
----------------
- Params are **pure data** (dataclasses); no Playwright / UI code here.
- :class:`CollectorSession` receives a :class:`ScenarioParams` instance
  and dispatches the correct ``ui_monitor`` setter calls.
- Adding a new scenario = add one new file in this package + one ``elif``
  in :meth:`CollectorSession._apply_params`.

Example::

    from lib.testtool.phm.scenarios.modern_standby_cycling import (
        ModernStandbyCyclingParams,
    )

    params = ModernStandbyCyclingParams(
        delayed_start_seconds=10,
        scenario_duration_minutes=2,
        cycle_count=5,
    )
    print(params.scenario_name)   # "Modern Standby Cycling"
    print(params.to_dict())
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, Dict


class ScenarioParams(ABC):
    """
    Abstract base for all PHM Collector Preset Scenario parameter objects.

    Concrete subclasses **must** be decorated with ``@dataclasses.dataclass``
    and implement the :attr:`scenario_name` property.

    Attributes:
        scenario_name: The exact text label of the scenario's radio button
                       in the PHM web UI  (used for element selection).
    """

    @property
    @abstractmethod
    def scenario_name(self) -> str:
        """
        Return the exact UI label for this scenario's radio button.

        The string is used by :class:`PHMUIMonitor.select_preset_scenario`
        to locate and click the correct radio button.
        """
        ...

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialise all dataclass fields to a plain dict.

        Returns:
            Dict mapping field name → value, suitable for logging or JSON.

        Raises:
            TypeError: If the subclass is not a dataclass.
        """
        if not dataclasses.is_dataclass(self):
            raise TypeError(
                f"{type(self).__name__} must be decorated with @dataclasses.dataclass"
            )
        return dataclasses.asdict(self)

    def __repr__(self) -> str:  # pragma: no cover
        fields = ", ".join(
            f"{f.name}={getattr(self, f.name)!r}"
            for f in dataclasses.fields(self)  # type: ignore[arg-type]
        )
        return f"{type(self).__name__}({fields})"
