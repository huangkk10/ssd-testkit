"""
Unit tests for windows_adk UIRunner.

All pywinauto / psutil interactions are mocked — no real GUI or process needed.
"""

import pytest
from unittest.mock import MagicMock, Mock, call, patch

from lib.testtool.windows_adk.exceptions import ADKUIError
from lib.testtool.windows_adk.ui_runner import UIRunner


@pytest.fixture
def runner():
    return UIRunner()


@pytest.fixture
def mock_app():
    app = MagicMock()
    window = MagicMock()
    app.window.return_value = window
    window.exists.return_value = True
    return app, window


# ---------------------------------------------------------------------------
# open / close / connect
# ---------------------------------------------------------------------------

class TestOpen:
    def test_open_starts_application(self, runner):
        with patch("lib.testtool.windows_adk.ui_runner.Application") as MockApp:
            mock_app = MagicMock()
            mock_window = MagicMock()
            mock_window.exists.return_value = True
            mock_app.window.return_value = mock_window
            MockApp.return_value.start.return_value = mock_app

            runner.open("C:\\fake\\wac.exe")

            MockApp.return_value.start.assert_called_once_with("C:\\fake\\wac.exe")

    def test_open_maximizes_window(self, runner):
        with patch("lib.testtool.windows_adk.ui_runner.Application") as MockApp:
            mock_app = MagicMock()
            mock_window = MagicMock()
            mock_window.exists.return_value = True
            mock_app.window.return_value = mock_window
            MockApp.return_value.start.return_value = mock_app

            runner.open("C:\\fake\\wac.exe")

            mock_window.maximize.assert_called()

    def test_open_raises_on_failure(self, runner):
        with patch("lib.testtool.windows_adk.ui_runner.Application") as MockApp:
            MockApp.return_value.start.side_effect = RuntimeError("no wac")
            with pytest.raises(ADKUIError):
                runner.open("C:\\fake\\wac.exe")


class TestClose:
    def test_close_kills_axe_exe(self, runner):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "axe.exe"
        runner._session.app = MagicMock()

        with patch("lib.testtool.windows_adk.ui_runner.psutil.process_iter", return_value=[mock_proc]):
            runner.close()

        mock_proc.kill.assert_called_once()

    def test_close_kills_wac_app(self, runner):
        mock_app = MagicMock()
        runner._session.app = mock_app

        with patch("lib.testtool.windows_adk.ui_runner.psutil.process_iter", return_value=[]):
            runner.close()

        mock_app.kill.assert_called_once()


# ---------------------------------------------------------------------------
# Assessment selection helpers
# ---------------------------------------------------------------------------

def _setup_runner_with_mock_window(runner):
    """Attach a MagicMock window to runner._session and return it."""
    mock_window = MagicMock()
    mock_ctrl = MagicMock()
    mock_window.child_window.return_value = mock_ctrl
    runner._session.window = mock_window
    return mock_window, mock_ctrl


class TestSelectBpfs:
    def test_select_bpfs_calls_run_button(self, runner):
        mock_window, mock_ctrl = _setup_runner_with_mock_window(runner)
        with patch("lib.testtool.windows_adk.ui_runner.time.sleep"):
            runner.select_bpfs()
        # Run button should be clicked
        mock_ctrl.click.assert_called()

    def test_select_bpfb_calls_run_button(self, runner):
        mock_window, mock_ctrl = _setup_runner_with_mock_window(runner)
        with patch("lib.testtool.windows_adk.ui_runner.time.sleep"):
            runner.select_bpfb()
        mock_ctrl.click.assert_called()

    def test_select_standby_calls_run_button(self, runner):
        mock_window, mock_ctrl = _setup_runner_with_mock_window(runner)
        with patch("lib.testtool.windows_adk.ui_runner.time.sleep"):
            with patch("lib.testtool.windows_adk.ui_runner.keyboard.send_keys"):
                runner.select_standby()
        mock_ctrl.click.assert_called()

    def test_select_hibernate_calls_run_button(self, runner):
        mock_window, mock_ctrl = _setup_runner_with_mock_window(runner)
        with patch("lib.testtool.windows_adk.ui_runner.time.sleep"):
            runner.select_hibernate()
        mock_ctrl.click.assert_called()


# ---------------------------------------------------------------------------
# _kill_process
# ---------------------------------------------------------------------------

class TestKillProcess:
    def test_kills_matching_process(self, runner):
        proc = MagicMock()
        proc.name.return_value = "axe.exe"
        with patch("lib.testtool.windows_adk.ui_runner.psutil.process_iter", return_value=[proc]):
            runner._kill_process("axe.exe")
        proc.kill.assert_called_once()

    def test_skips_non_matching_process(self, runner):
        proc = MagicMock()
        proc.name.return_value = "notepad.exe"
        with patch("lib.testtool.windows_adk.ui_runner.psutil.process_iter", return_value=[proc]):
            runner._kill_process("axe.exe")
        proc.kill.assert_not_called()
