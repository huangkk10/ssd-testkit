"""
Unit tests for PHM Collector Scenario system:

- ScenarioParams (base)
- ModernStandbyCyclingParams
- build_scenario_params factory
- CollectorSession (with mocked PHMUIMonitor)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, call, patch

# ── Subjects under test ───────────────────────────────────────────────
from lib.testtool.phm.scenarios.base import ScenarioParams
from lib.testtool.phm.scenarios.modern_standby_cycling import (
    ModernStandbyCyclingParams,
)
from lib.testtool.phm.scenarios import (
    build_scenario_params,
    registered_scenario_types,
)
from lib.testtool.phm.collector_session import CollectorSession
from lib.testtool.phm.exceptions import PHMUIError


# ======================================================================
# ScenarioParams — base
# ======================================================================

class TestScenarioParamsBase:
    """ScenarioParams is abstract; verify subclass contract."""

    def test_scenario_params_is_abstract(self):
        """Cannot instantiate ScenarioParams directly."""
        with pytest.raises(TypeError):
            ScenarioParams()  # type: ignore[abstract]

    def test_to_dict_requires_dataclass(self):
        """to_dict() raises TypeError for non-dataclass subclasses."""

        class BadParams(ScenarioParams):
            @property
            def scenario_name(self) -> str:
                return "Bad"

        obj = BadParams()
        with pytest.raises(TypeError, match="dataclass"):
            obj.to_dict()


# ======================================================================
# ModernStandbyCyclingParams
# ======================================================================

class TestModernStandbyCyclingParams:

    def test_default_values(self):
        p = ModernStandbyCyclingParams()
        assert p.delayed_start_seconds == 10
        assert p.scenario_duration_minutes == 1
        assert p.cycle_count == 10

    def test_custom_values(self):
        p = ModernStandbyCyclingParams(
            delayed_start_seconds=5,
            scenario_duration_minutes=3,
            cycle_count=20,
        )
        assert p.delayed_start_seconds == 5
        assert p.scenario_duration_minutes == 3
        assert p.cycle_count == 20

    def test_scenario_name(self):
        assert ModernStandbyCyclingParams().scenario_name == "Modern Standby Cycling"

    def test_to_dict_returns_all_fields(self):
        p = ModernStandbyCyclingParams(
            delayed_start_seconds=7,
            scenario_duration_minutes=2,
            cycle_count=4,
        )
        d = p.to_dict()
        assert d == {
            "delayed_start_seconds": 7,
            "scenario_duration_minutes": 2,
            "cycle_count": 4,
        }

    # ── Validation ──────────────────────────────────────────────────────

    def test_negative_delayed_start_raises(self):
        with pytest.raises(ValueError, match="delayed_start_seconds"):
            ModernStandbyCyclingParams(delayed_start_seconds=-1)

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError, match="scenario_duration_minutes"):
            ModernStandbyCyclingParams(scenario_duration_minutes=0)

    def test_zero_cycle_count_raises(self):
        with pytest.raises(ValueError, match="cycle_count"):
            ModernStandbyCyclingParams(cycle_count=0)

    def test_is_scenario_params(self):
        assert isinstance(ModernStandbyCyclingParams(), ScenarioParams)


# ======================================================================
# build_scenario_params factory
# ======================================================================

class TestBuildScenarioParams:

    def test_modern_standby_cycling_defaults(self):
        cfg = {"scenario_type": "modern_standby_cycling"}
        p = build_scenario_params(cfg)
        assert isinstance(p, ModernStandbyCyclingParams)
        assert p.delayed_start_seconds == 10
        assert p.scenario_duration_minutes == 1
        assert p.cycle_count == 10

    def test_modern_standby_cycling_custom(self):
        cfg = {
            "scenario_type": "modern_standby_cycling",
            "delayed_start_seconds": 5,
            "scenario_duration_minutes": 3,
            "cycle_count": 20,
        }
        p = build_scenario_params(cfg)
        assert p.delayed_start_seconds == 5
        assert p.scenario_duration_minutes == 3
        assert p.cycle_count == 20

    def test_default_scenario_type_when_missing(self):
        """scenario_type defaults to 'modern_standby_cycling'."""
        p = build_scenario_params({})
        assert isinstance(p, ModernStandbyCyclingParams)

    def test_unknown_scenario_type_raises(self):
        with pytest.raises(ValueError, match="Unknown scenario_type"):
            build_scenario_params({"scenario_type": "nonexistent_scenario"})

    def test_extra_cfg_keys_are_ignored(self):
        """Full PHMConfig dict should not cause KeyError."""
        cfg = {
            "scenario_type": "modern_standby_cycling",
            "installer_path": "./bin/phm.exe",
            "cycle_count": 5,
            "delayed_start_seconds": 2,
            "scenario_duration_minutes": 1,
            "timeout": 3600,
            "log_path": "./testlog",
        }
        p = build_scenario_params(cfg)
        assert isinstance(p, ModernStandbyCyclingParams)
        assert p.cycle_count == 5

    def test_registered_scenario_types_contains_modern_standby_cycling(self):
        assert "modern_standby_cycling" in registered_scenario_types()


# ======================================================================
# CollectorSession
# ======================================================================

class TestCollectorSession:
    """All browser interactions are replaced by a MagicMock ui_monitor."""

    @pytest.fixture
    def mock_ui(self):
        ui = MagicMock()
        return ui

    @pytest.fixture
    def session(self, mock_ui):
        return CollectorSession(mock_ui)

    # ── run() happy path ────────────────────────────────────────────────

    def test_run_calls_navigate_to_collector(self, session, mock_ui):
        session.run(ModernStandbyCyclingParams())
        mock_ui.navigate_to_collector.assert_called_once()

    def test_run_calls_expand_collection_options(self, session, mock_ui):
        session.run(ModernStandbyCyclingParams())
        mock_ui.expand_collection_options.assert_called_once()

    def test_run_calls_select_preset_scenario_with_correct_name(
        self, session, mock_ui
    ):
        session.run(ModernStandbyCyclingParams())
        mock_ui.select_preset_scenario.assert_called_once_with(
            "Modern Standby Cycling"
        )

    def test_run_sets_delayed_start(self, session, mock_ui):
        session.run(ModernStandbyCyclingParams(delayed_start_seconds=7))
        mock_ui.set_delayed_start.assert_called_once_with(7)

    def test_run_sets_scenario_duration(self, session, mock_ui):
        session.run(ModernStandbyCyclingParams(scenario_duration_minutes=3))
        mock_ui.set_scenario_duration.assert_called_once_with(3)

    def test_run_sets_cycle_count(self, session, mock_ui):
        session.run(ModernStandbyCyclingParams(cycle_count=15))
        mock_ui.set_cycle_count.assert_called_once_with(15)

    def test_run_calls_start_test(self, session, mock_ui):
        session.run(ModernStandbyCyclingParams())
        mock_ui.start_test.assert_called_once()

    def test_run_call_order(self, session, mock_ui):
        """Verify the exact sequence of UI calls."""
        session.run(
            ModernStandbyCyclingParams(
                delayed_start_seconds=5,
                scenario_duration_minutes=2,
                cycle_count=8,
            )
        )
        expected = [
            call.navigate_to_collector(),
            call.expand_collection_options(),
            call.select_preset_scenario("Modern Standby Cycling"),
            call.set_delayed_start(5),
            call.set_scenario_duration(2),
            call.set_cycle_count(8),
            call.start_test(),
        ]
        mock_ui.assert_has_calls(expected, any_order=False)

    # ── run() error paths ───────────────────────────────────────────────

    def test_run_raises_type_error_for_non_params(self, session):
        with pytest.raises(TypeError, match="ScenarioParams"):
            session.run("not a params object")  # type: ignore[arg-type]

    def test_run_propagates_ui_error_from_navigate(self, session, mock_ui):
        mock_ui.navigate_to_collector.side_effect = PHMUIError("nav failed")
        with pytest.raises(PHMUIError, match="nav failed"):
            session.run(ModernStandbyCyclingParams())

    def test_run_propagates_ui_error_from_start(self, session, mock_ui):
        mock_ui.start_test.side_effect = PHMUIError("start failed")
        with pytest.raises(PHMUIError, match="start failed"):
            session.run(ModernStandbyCyclingParams())

    def test_apply_params_unknown_type_raises_not_implemented(
        self, session
    ):
        """_apply_params must raise NotImplementedError for unknown types."""
        import dataclasses

        @dataclasses.dataclass
        class UnknownParams(ScenarioParams):
            @property
            def scenario_name(self) -> str:
                return "Unknown"

        with pytest.raises(NotImplementedError):
            session._apply_params(UnknownParams())


# ======================================================================
# PHMConfig — new scenario params keys
# ======================================================================

class TestPHMConfigScenarioKeys:

    def test_scenario_type_in_default_config(self):
        from lib.testtool.phm.config import PHMConfig
        cfg = PHMConfig.get_default_config()
        assert "scenario_type" in cfg
        assert cfg["scenario_type"] == "modern_standby_cycling"

    def test_delayed_start_seconds_in_default_config(self):
        from lib.testtool.phm.config import PHMConfig
        cfg = PHMConfig.get_default_config()
        assert "delayed_start_seconds" in cfg
        assert isinstance(cfg["delayed_start_seconds"], int)

    def test_scenario_duration_minutes_in_default_config(self):
        from lib.testtool.phm.config import PHMConfig
        cfg = PHMConfig.get_default_config()
        assert "scenario_duration_minutes" in cfg
        assert isinstance(cfg["scenario_duration_minutes"], int)

    def test_validate_accepts_new_keys(self):
        from lib.testtool.phm.config import PHMConfig
        assert PHMConfig.validate_config({
            "scenario_type": "modern_standby_cycling",
            "delayed_start_seconds": 5,
            "scenario_duration_minutes": 2,
        }) is True

    def test_validate_rejects_wrong_type_for_delayed_start(self):
        from lib.testtool.phm.config import PHMConfig
        from lib.testtool.phm.exceptions import PHMConfigError
        with pytest.raises(PHMConfigError):
            PHMConfig.validate_config({"delayed_start_seconds": "ten"})
