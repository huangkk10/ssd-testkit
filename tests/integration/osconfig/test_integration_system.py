"""
Integration tests — System Actions.

Tests FastStartupAction, NotificationAction, CortanaAction,
BackgroundAppsAction on a real machine.
All are registry-based and immediately reversible.
"""

import pytest

from lib.testtool.osconfig.actions.fast_startup import FastStartupAction
from lib.testtool.osconfig.actions.notifications import NotificationAction
from lib.testtool.osconfig.actions.cortana import CortanaAction
from lib.testtool.osconfig.actions.background_apps import BackgroundAppsAction

pytestmark = [pytest.mark.integration, pytest.mark.admin]


def _registry_cycle(action_cls, build_info) -> None:
    """Generic apply → check → revert cycle for a registry-based action."""
    if not action_cls.supported_on(build_info):
        pytest.skip(f"{action_cls.__name__} not supported on this build")

    action = action_cls()
    try:
        action.apply()
        assert action.check() is True, (
            f"{action_cls.__name__}.check() False immediately after apply()"
        )
    finally:
        action.revert()

    # After revert, check() should be False (setting restored to original)
    assert action.check() is False, (
        f"{action_cls.__name__}.check() still True after revert()"
    )


class TestFastStartupIntegration:

    def test_apply_check_revert(self, build_info):
        _registry_cycle(FastStartupAction, build_info)

    def test_apply_idempotent(self, build_info):
        if not FastStartupAction.supported_on(build_info):
            pytest.skip()
        action = FastStartupAction()
        try:
            action.apply()
            action.apply()   # second apply must not raise or re-write
            assert action.check() is True
        finally:
            action.revert()


class TestNotificationIntegration:

    def test_apply_check_revert(self, build_info):
        _registry_cycle(NotificationAction, build_info)


class TestCortanaIntegration:

    def test_apply_check_revert(self, build_info):
        _registry_cycle(CortanaAction, build_info)

    def test_revert_cleans_up_policy_key(self, build_info):
        """After revert, the policy value is removed (not just set to original)."""
        if not CortanaAction.supported_on(build_info):
            pytest.skip()

        action = CortanaAction()
        try:
            action.apply()
            assert action.check() is True
        finally:
            action.revert()

        # check() reading absent value → False
        assert action.check() is False


class TestBackgroundAppsIntegration:

    def test_apply_check_revert(self, build_info):
        _registry_cycle(BackgroundAppsAction, build_info)
