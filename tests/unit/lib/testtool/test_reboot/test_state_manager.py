"""
Unit tests for lib.testtool.reboot.state_manager.OsRebootStateManager.
"""
import json
import pytest

from lib.testtool.reboot.state_manager import OsRebootStateManager
from lib.testtool.reboot.exceptions import OsRebootStateError


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture
def manager(tmp_path):
    return OsRebootStateManager(str(tmp_path / 'state.json'))


@pytest.fixture
def recovering_manager(tmp_path):
    """Manager whose state file already contains is_recovering=True."""
    path = tmp_path / 'state.json'
    path.write_text(
        json.dumps({
            'is_recovering': True,
            'current_cycle':  1,
            'total_cycles':   3,
            'last_reboot_timestamp': '2026-03-02T10:00:00',
        }),
        encoding='utf-8',
    )
    return OsRebootStateManager(str(path))


# ------------------------------------------------------------------ #
# load                                                                 #
# ------------------------------------------------------------------ #

class TestLoad:
    def test_returns_default_when_no_file(self, manager):
        state = manager.load()
        assert state['is_recovering'] is False
        assert state['current_cycle'] == 0
        assert state['total_cycles'] == 0

    def test_loads_saved_state(self, manager):
        manager.save({'is_recovering': True, 'current_cycle': 2, 'total_cycles': 3})
        state = manager.load()
        assert state['is_recovering'] is True
        assert state['current_cycle'] == 2

    def test_raises_on_corrupt_json(self, tmp_path):
        bad_path = tmp_path / 'bad.json'
        bad_path.write_text('{ not valid json }')
        mgr = OsRebootStateManager(str(bad_path))
        with pytest.raises(OsRebootStateError, match="Failed to load"):
            mgr.load()

    def test_back_fills_missing_keys(self, tmp_path):
        """State files missing optional keys are back-filled with defaults."""
        path = tmp_path / 'partial.json'
        path.write_text(json.dumps({'current_cycle': 5}), encoding='utf-8')
        mgr   = OsRebootStateManager(str(path))
        state = mgr.load()
        assert 'is_recovering' in state
        assert state['current_cycle'] == 5


# ------------------------------------------------------------------ #
# save                                                                 #
# ------------------------------------------------------------------ #

class TestSave:
    def test_creates_file(self, manager, tmp_path):
        assert not (tmp_path / 'state.json').exists()
        manager.save({'is_recovering': True, 'current_cycle': 1, 'total_cycles': 2})
        assert (tmp_path / 'state.json').exists()

    def test_injects_timestamp(self, manager):
        manager.save({'is_recovering': False, 'current_cycle': 0, 'total_cycles': 1})
        state = manager.load()
        assert state['last_reboot_timestamp'] is not None

    def test_roundtrip(self, manager):
        payload = {'is_recovering': True, 'current_cycle': 2, 'total_cycles': 4}
        manager.save(payload)
        loaded = manager.load()
        assert loaded['is_recovering'] is True
        assert loaded['current_cycle'] == 2
        assert loaded['total_cycles'] == 4

    def test_creates_parent_dirs(self, tmp_path):
        deep_path = tmp_path / 'a' / 'b' / 'c' / 'state.json'
        mgr = OsRebootStateManager(str(deep_path))
        mgr.save({'is_recovering': False, 'current_cycle': 0, 'total_cycles': 1})
        assert deep_path.exists()


# ------------------------------------------------------------------ #
# clear                                                                #
# ------------------------------------------------------------------ #

class TestClear:
    def test_removes_file(self, manager, tmp_path):
        manager.save({'is_recovering': False, 'current_cycle': 0, 'total_cycles': 1})
        assert (tmp_path / 'state.json').exists()
        manager.clear()
        assert not (tmp_path / 'state.json').exists()

    def test_no_error_when_no_file(self, manager):
        manager.clear()   # should not raise


# ------------------------------------------------------------------ #
# is_recovering                                                        #
# ------------------------------------------------------------------ #

class TestIsRecovering:
    def test_false_when_no_file(self, manager):
        assert manager.is_recovering() is False

    def test_true_when_flag_set(self, recovering_manager):
        assert recovering_manager.is_recovering() is True

    def test_false_after_clear(self, recovering_manager):
        recovering_manager.clear()
        assert recovering_manager.is_recovering() is False

    def test_false_on_corrupt_file(self, tmp_path):
        bad = tmp_path / 'bad.json'
        bad.write_text('not json')
        mgr = OsRebootStateManager(str(bad))
        assert mgr.is_recovering() is False   # does not raise
