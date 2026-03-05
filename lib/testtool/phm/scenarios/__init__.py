"""
PHM Collector — Scenarios Package

Public API::

    from lib.testtool.phm.scenarios import (
        ScenarioParams,
        ModernStandbyCyclingParams,
        build_scenario_params,
    )

Factory
-------
:func:`build_scenario_params` converts a flat ``PHMConfig`` dict (or any
``dict`` containing ``scenario_type`` and the relevant parameter keys) into
the appropriate :class:`ScenarioParams` subclass instance.

This keeps ``PHMController`` independent of concrete scenario types —
it only calls ``build_scenario_params(cfg)`` and passes the result to
:class:`CollectorSession`.

Extending
---------
To add a new scenario (e.g. *Idle Screen On*):

1. Create ``lib/testtool/phm/scenarios/idle_screen_on.py`` with
   ``@dataclass class IdleScreenOnParams(ScenarioParams)``.
2. Import it here and add an ``elif`` branch in :func:`build_scenario_params`.
3. That's it — no other files need to change.
"""

from .base import ScenarioParams
from .modern_standby_cycling import ModernStandbyCyclingParams

__all__ = [
    "ScenarioParams",
    "ModernStandbyCyclingParams",
    "build_scenario_params",
]

# Registry: scenario_type string  →  (class, required_config_keys)
# Keeping it as a dict makes it easy to introspect / extend.
_SCENARIO_REGISTRY: dict = {
    "modern_standby_cycling": ModernStandbyCyclingParams,
    # Future entries:
    # "idle_screen_on":      IdleScreenOnParams,
    # "video_playback":      VideoPlaybackParams,
    # "modern_standby":      ModernStandbyParams,
    # "idle_screen_off":     IdleScreenOffParams,
}


def build_scenario_params(cfg: dict) -> ScenarioParams:
    """
    Construct the correct :class:`ScenarioParams` instance from a config dict.

    The ``scenario_type`` key in *cfg* selects the scenario class.
    Remaining relevant keys are forwarded as constructor arguments.

    Args:
        cfg: A dict that must contain ``scenario_type`` and all parameter
             keys required by the selected scenario class.  Extra keys are
             silently ignored (allows passing the full ``PHMConfig`` dict).

    Returns:
        A validated :class:`ScenarioParams` instance.

    Raises:
        KeyError:  If ``scenario_type`` is missing from *cfg*.
        ValueError: If ``scenario_type`` is not registered or a field
                    value fails validation.

    Example::

        cfg = {
            'scenario_type':             'modern_standby_cycling',
            'delayed_start_seconds':     10,
            'scenario_duration_minutes': 2,
            'cycle_count':               5,
        }
        params = build_scenario_params(cfg)
        assert isinstance(params, ModernStandbyCyclingParams)
    """
    stype = cfg.get("scenario_type", "modern_standby_cycling")
    cls = _SCENARIO_REGISTRY.get(stype)
    if cls is None:
        registered = ", ".join(f"'{k}'" for k in _SCENARIO_REGISTRY)
        raise ValueError(
            f"Unknown scenario_type '{stype}'. "
            f"Registered types: {registered}"
        )

    if cls is ModernStandbyCyclingParams:
        return ModernStandbyCyclingParams(
            delayed_start_seconds=int(cfg.get("delayed_start_seconds", 10)),
            scenario_duration_minutes=int(cfg.get("scenario_duration_minutes", 1)),
            cycle_count=int(cfg.get("cycle_count", 10)),
        )

    # Future scenarios: add elif blocks here following the same pattern.
    # The dispatcher is intentionally explicit (not **kwargs magic) so that
    # each scenario's required fields are obvious and type-checked.
    raise NotImplementedError(
        f"build_scenario_params: dispatch for '{stype}' is not yet implemented."
    )


def registered_scenario_types() -> list:
    """Return a sorted list of all registered scenario_type strings."""
    return sorted(_SCENARIO_REGISTRY.keys())
