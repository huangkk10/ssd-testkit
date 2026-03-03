"""
Unit tests for OsConfigProfile (config.py).
"""

import pytest
from dataclasses import fields

from lib.testtool.osconfig.config import OsConfigProfile


class TestOsConfigProfileDefaults:

    def test_all_bool_fields_default_false(self):
        profile = OsConfigProfile()
        for f in fields(profile):
            if f.type == "bool":
                assert getattr(profile, f.name) is False, (
                    f"Field {f.name!r} should default to False"
                )

    def test_power_plan_defaults_empty_string(self):
        assert OsConfigProfile().power_plan == ""

    def test_pagefile_drive_default(self):
        assert OsConfigProfile().pagefile_drive == "C:"

    def test_pagefile_min_mb_default(self):
        assert OsConfigProfile().pagefile_min_mb == 4096

    def test_pagefile_max_mb_default(self):
        assert OsConfigProfile().pagefile_max_mb == 8192

    def test_fail_on_unsupported_defaults_false(self):
        assert OsConfigProfile().fail_on_unsupported is False

    def test_empty_profile_enabled_actions_is_empty(self):
        assert OsConfigProfile().enabled_actions() == []


class TestOsConfigProfileDefault:

    def test_default_returns_profile(self):
        assert isinstance(OsConfigProfile.default(), OsConfigProfile)

    def test_default_all_bool_fields_true(self):
        profile = OsConfigProfile.default()
        skip = {"fail_on_unsupported", "power_plan",
                "pagefile_drive", "pagefile_min_mb", "pagefile_max_mb"}
        for f in fields(profile):
            if f.name in skip:
                continue
            if f.type == "bool":
                assert getattr(profile, f.name) is True, (
                    f"OsConfigProfile.default() field {f.name!r} should be True"
                )

    def test_default_power_plan_is_high_performance(self):
        assert OsConfigProfile.default().power_plan == "high_performance"

    def test_default_pagefile_drive(self):
        assert OsConfigProfile.default().pagefile_drive == "C:"

    def test_default_pagefile_sizes(self):
        p = OsConfigProfile.default()
        assert p.pagefile_min_mb == 4096
        assert p.pagefile_max_mb == 8192

    def test_default_enabled_actions_non_empty(self):
        assert len(OsConfigProfile.default().enabled_actions()) > 0


class TestOsConfigProfileEnabledActions:

    def test_single_bool_action(self):
        p = OsConfigProfile(disable_search_index=True)
        names = [name for name, _ in p.enabled_actions()]
        assert "disable_search_index" in names

    def test_power_plan_appears_when_non_empty(self):
        p = OsConfigProfile(power_plan="balanced")
        names = [name for name, _ in p.enabled_actions()]
        assert "power_plan" in names

    def test_power_plan_absent_when_empty(self):
        p = OsConfigProfile(power_plan="")
        names = [name for name, _ in p.enabled_actions()]
        assert "power_plan" not in names

    def test_pagefile_params_not_in_enabled_actions(self):
        p = OsConfigProfile(manage_pagefile=True,
                            pagefile_drive="D:", pagefile_min_mb=1024)
        names = [name for name, _ in p.enabled_actions()]
        assert "pagefile_drive" not in names
        assert "pagefile_min_mb" not in names
        assert "pagefile_max_mb" not in names
        assert "manage_pagefile" in names

    def test_fail_on_unsupported_not_in_enabled_actions(self):
        p = OsConfigProfile(fail_on_unsupported=True)
        names = [name for name, _ in p.enabled_actions()]
        assert "fail_on_unsupported" not in names

    def test_count_all_enabled_matches_default(self):
        p = OsConfigProfile.default()
        enabled = p.enabled_actions()
        # 6 services + 6 security + 5 boot + 1 power_plan + 6 power_timeouts +
        # 2 schedule + 6 system = 32 enabled entries
        assert len(enabled) == 32


class TestOsConfigProfileCustomisation:

    def test_partial_profile(self):
        p = OsConfigProfile(
            disable_search_index=True,
            disable_windows_update=True,
            power_plan="high_performance",
        )
        names = [n for n, _ in p.enabled_actions()]
        assert "disable_search_index" in names
        assert "disable_windows_update" in names
        assert "power_plan" in names
        assert "disable_sysmain" not in names

    def test_profile_is_mutable(self):
        p = OsConfigProfile()
        p.disable_cortana = True
        assert p.disable_cortana is True

    def test_two_profiles_independent(self):
        a = OsConfigProfile(disable_defender=True)
        b = OsConfigProfile()
        assert a.disable_defender is True
        assert b.disable_defender is False
