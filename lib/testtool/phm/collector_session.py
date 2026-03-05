"""
PHM Collector Session

Encapsulates the complete step-by-step workflow for one Collector run:

    1. Navigate to the Collector tab
    2. Expand the Collection Options accordion
    3. Select the target Preset Scenario (radio button)
    4. Apply scenario-specific parameters (inputs)
    5. Click Start

This class acts as the bridge between the high-level
:class:`PHMController` (which only knows about a :class:`ScenarioParams`
instance) and the low-level :class:`PHMUIMonitor` (which fires individual
Playwright commands).

Design
------
- :meth:`run` is the single public entry point; the caller passes a
  :class:`ScenarioParams` subclass instance and everything else is handled
  automatically.
- :meth:`_apply_params` dispatches on the concrete type of the params
  object.  To support a new scenario, add one ``elif`` branch here.
- No Playwright imports live here; all browser interactions are
  delegated to ``ui_monitor``.

Usage::

    from lib.testtool.phm.collector_session import CollectorSession
    from lib.testtool.phm.scenarios import ModernStandbyCyclingParams

    session = CollectorSession(ui_monitor)
    session.run(
        ModernStandbyCyclingParams(
            delayed_start_seconds=10,
            scenario_duration_minutes=2,
            cycle_count=5,
        )
    )
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.logger import get_module_logger
from .exceptions import PHMUIError
from .scenarios.base import ScenarioParams
from .scenarios.modern_standby_cycling import ModernStandbyCyclingParams

if TYPE_CHECKING:
    from .ui_monitor import PHMUIMonitor

logger = get_module_logger(__name__)


class CollectorSession:
    """
    Orchestrates a single PHM Collector test run.

    Args:
        ui_monitor: A connected (browser open) :class:`PHMUIMonitor` instance.

    Example::

        monitor = PHMUIMonitor(host='localhost', port=1337)
        monitor.wait_for_ready()
        monitor.open_browser()

        session = CollectorSession(monitor)
        session.run(
            ModernStandbyCyclingParams(
                delayed_start_seconds=10,
                scenario_duration_minutes=2,
                cycle_count=5,
            )
        )

        monitor.wait_for_completion(timeout=3600)
        monitor.close_browser()
    """

    def __init__(self, ui_monitor: "PHMUIMonitor") -> None:
        self._ui = ui_monitor

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, params: ScenarioParams) -> None:
        """
        Execute the full Collector setup sequence and click Start.

        Args:
            params: A :class:`ScenarioParams` instance describing which
                    scenario to select and what values to configure.

        Raises:
            PHMUIError:  Any UI interaction failure (element not found,
                         Playwright timeout, etc.).
            TypeError:   If *params* is not a :class:`ScenarioParams`.
        """
        if not isinstance(params, ScenarioParams):
            raise TypeError(
                f"params must be a ScenarioParams instance, got {type(params)}"
            )

        logger.info(
            f"CollectorSession.run — scenario='{params.scenario_name}' "
            f"params={params.to_dict()}"
        )

        # Step 1: Collector tab
        self._ui.navigate_to_collector()

        # Step 2: Expand Collection Options
        self._ui.expand_collection_options()

        # Step 3: Select the scenario radio button
        self._ui.select_preset_scenario(params.scenario_name)

        # Step 4: Fill in the scenario-specific parameter fields
        self._apply_params(params)

        # Step 5: Start
        self._ui.start_test()
        logger.info("CollectorSession: Start clicked — test is running")

    # ------------------------------------------------------------------
    # Parameter dispatch
    # ------------------------------------------------------------------

    def _apply_params(self, params: ScenarioParams) -> None:
        """
        Dispatch parameter-setting calls based on the concrete params type.

        Each scenario type maps to a specific set of UI fields.  Adding
        support for a new scenario only requires an ``elif`` block here
        (plus the new :class:`ScenarioParams` subclass).

        Args:
            params: Validated :class:`ScenarioParams` instance.

        Raises:
            PHMUIError:        If a setter call fails.
            NotImplementedError: If the params type has no dispatch entry.
        """
        if isinstance(params, ModernStandbyCyclingParams):
            self._apply_modern_standby_cycling(params)

        # ----------------------------------------------------------------
        # Future scenarios — add elif branches here:
        #
        # elif isinstance(params, IdleScreenOnParams):
        #     self._apply_idle_screen_on(params)
        #
        # elif isinstance(params, VideoPlaybackParams):
        #     self._apply_video_playback(params)
        #
        # elif isinstance(params, ModernStandbyParams):
        #     self._apply_modern_standby(params)
        #
        # elif isinstance(params, IdleScreenOffParams):
        #     self._apply_idle_screen_off(params)
        # ----------------------------------------------------------------

        else:
            raise NotImplementedError(
                f"CollectorSession._apply_params: no dispatch for "
                f"'{type(params).__name__}'. "
                "Add an elif branch and the corresponding _apply_* method."
            )

    # ------------------------------------------------------------------
    # Per-scenario apply helpers
    # ------------------------------------------------------------------

    def _apply_modern_standby_cycling(
        self, params: ModernStandbyCyclingParams
    ) -> None:
        """Set Delayed Start, Scenario Duration, and Cycle Count fields."""
        logger.info(
            f"Applying Modern Standby Cycling params: "
            f"delayed_start={params.delayed_start_seconds}s, "
            f"duration={params.scenario_duration_minutes}min, "
            f"cycles={params.cycle_count}"
        )
        self._ui.set_delayed_start(params.delayed_start_seconds)
        self._ui.set_scenario_duration(params.scenario_duration_minutes)
        self._ui.set_cycle_count(params.cycle_count)
