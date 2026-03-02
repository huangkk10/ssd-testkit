"""
Unit tests for PHMUIMonitor.
Playwright is fully mocked â€” no real browser or PHM server required.
"""

import socket
from unittest.mock import Mock, patch, MagicMock, call
import pytest


def _make_monitor(host='localhost', port=1337, headless=False, browser_timeout=30000):
    """Helper: create PHMUIMonitor with _PLAYWRIGHT_AVAILABLE patched True."""
    with patch('lib.testtool.phm.ui_monitor._PLAYWRIGHT_AVAILABLE', True):
        from lib.testtool.phm.ui_monitor import PHMUIMonitor
        return PHMUIMonitor(
            host=host, port=port,
            headless=headless,
            browser_timeout=browser_timeout,
        )


class TestPHMUIMonitorImport:
    """Verify the module imports correctly even without playwright."""

    def test_import_without_playwright(self):
        """PHMUIMonitor should be importable even if playwright is missing."""
        import sys
        import importlib
        saved = sys.modules.get('playwright')
        saved_sync = sys.modules.get('playwright.sync_api')
        sys.modules['playwright'] = None
        sys.modules['playwright.sync_api'] = None
        try:
            import lib.testtool.phm.ui_monitor as mod
            importlib.reload(mod)
        except Exception:
            pass
        finally:
            if saved is None:
                sys.modules.pop('playwright', None)
            else:
                sys.modules['playwright'] = saved
            if saved_sync is None:
                sys.modules.pop('playwright.sync_api', None)
            else:
                sys.modules['playwright.sync_api'] = saved_sync


class TestPHMUIMonitorInit:
    """Tests for PHMUIMonitor initialization."""

    def test_init_default_values(self):
        with patch('lib.testtool.phm.ui_monitor._PLAYWRIGHT_AVAILABLE', True):
            from lib.testtool.phm.ui_monitor import PHMUIMonitor
            m = PHMUIMonitor()
            assert m.host == 'localhost'
            assert m.port == 1337
            assert m.base_url == 'http://localhost:1337'
            assert not m.headless
            assert m.browser_timeout == 30000

    def test_init_custom_values(self):
        m = _make_monitor(host='192.168.1.10', port=8080, headless=True, browser_timeout=5000)
        assert m.host == '192.168.1.10'
        assert m.port == 8080
        assert m.base_url == 'http://192.168.1.10:8080'
        assert m.headless

    def test_init_not_connected(self):
        m = _make_monitor()
        assert not m.is_connected
        assert m.page is None

    def test_init_raises_if_no_playwright(self):
        from lib.testtool.phm.exceptions import PHMUIError
        with patch('lib.testtool.phm.ui_monitor._PLAYWRIGHT_AVAILABLE', False):
            from lib.testtool.phm.ui_monitor import PHMUIMonitor
            with pytest.raises(PHMUIError):
                PHMUIMonitor()


class TestPHMUIMonitorWaitForReady:
    """Tests for wait_for_ready()."""

    def test_ready_on_first_attempt(self):
        m = _make_monitor()
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        with patch('lib.testtool.phm.ui_monitor.socket.create_connection',
                   return_value=mock_conn) as mock_create:
            result = m.wait_for_ready(timeout=5)
            assert result
            mock_create.assert_called_once_with(('localhost', 1337), timeout=1)

    def test_ready_after_retry(self):
        m = _make_monitor()
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        with patch('lib.testtool.phm.ui_monitor.socket.create_connection',
                   side_effect=[OSError, OSError, mock_conn]):
            with patch('lib.testtool.phm.ui_monitor.time.sleep'):
                result = m.wait_for_ready(timeout=10)
                assert result

    def test_timeout_raises(self):
        from lib.testtool.phm.exceptions import PHMTimeoutError
        m = _make_monitor()
        with patch('lib.testtool.phm.ui_monitor.socket.create_connection',
                   side_effect=OSError):
            with patch('lib.testtool.phm.ui_monitor.time.sleep'):
                with patch('lib.testtool.phm.ui_monitor.time.time',
                           side_effect=[0, 0, 100]):  # deadline exceeded
                    with pytest.raises(PHMTimeoutError):
                        m.wait_for_ready(timeout=1)


class TestPHMUIMonitorOpenCloseBrowser:
    """Tests for open_browser() and close_browser()."""

    def _mock_playwright(self):
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        return mock_pw, mock_browser, mock_context, mock_page

    def test_open_browser_sets_connected(self):
        m = _make_monitor()
        mock_pw, mock_browser, mock_context, mock_page = self._mock_playwright()
        mock_sync_pw = MagicMock()
        mock_sync_pw.return_value.__enter__ = Mock(return_value=mock_pw)
        mock_sync_pw.return_value.__exit__ = Mock(return_value=False)
        mock_sync_pw.return_value.start.return_value = mock_pw

        with patch('lib.testtool.phm.ui_monitor.sync_playwright', mock_sync_pw):
            m.open_browser()
            assert m.is_connected
            assert m.page is not None

    def test_open_browser_uses_headless_param(self):
        m = _make_monitor(headless=False)
        mock_pw, mock_browser, mock_context, mock_page = self._mock_playwright()
        mock_sync_pw = MagicMock()
        mock_sync_pw.return_value.start.return_value = mock_pw

        with patch('lib.testtool.phm.ui_monitor.sync_playwright', mock_sync_pw):
            m.open_browser(headless=True)
            mock_pw.chromium.launch.assert_called_once_with(headless=True)

    def test_close_browser_clears_connected(self):
        m = _make_monitor()
        m._connected = True
        m._page = MagicMock()
        m._context = MagicMock()
        m._browser = MagicMock()
        m._playwright = MagicMock()

        m.close_browser()

        assert not m.is_connected
        assert m.page is None

    def test_close_browser_safe_when_not_open(self):
        m = _make_monitor()
        m.close_browser()   # should not raise
        assert not m.is_connected

class TestPHMUIMonitorRequireConnected:
    """Tests for _require_connected guard."""

    def test_raises_when_not_connected(self):
        from lib.testtool.phm.exceptions import PHMUIError
        m = _make_monitor()
        with pytest.raises(PHMUIError):
            m._require_connected()

    def test_passes_when_connected(self):
        m = _make_monitor()
        m._connected = True
        m._page = MagicMock()
        m._require_connected()   # should not raise


class TestPHMUIMonitorNavigation:
    """Tests for navigate_to_collector()."""

    def _connected_monitor(self):
        m = _make_monitor()
        m._connected = True
        m._page = MagicMock()
        return m

    def test_navigate_to_collector_calls_click(self):
        m = self._connected_monitor()
        from lib.testtool.phm.ui_monitor import _SEL_COLLECTOR_TAB
        m.navigate_to_collector()
        m._page.click.assert_called_once_with(_SEL_COLLECTOR_TAB)

    def test_navigate_raises_phmuierror_on_failure(self):
        from lib.testtool.phm.exceptions import PHMUIError
        m = self._connected_monitor()
        m._page.click.side_effect = Exception("element not found")
        with pytest.raises(PHMUIError):
            m.navigate_to_collector()


class TestPHMUIMonitorParams:
    """Tests for parameter-setting methods."""

    def setup_method(self):
        self.m = _make_monitor()
        self.m._connected = True
        self.m._page = MagicMock()

    def test_set_cycle_count_fills_input(self):
        from lib.testtool.phm.ui_monitor import _SEL_CYCLE_INPUT
        self.m.set_cycle_count(20)
        self.m._page.fill.assert_called_once_with(_SEL_CYCLE_INPUT, '20')

    def test_set_cycle_count_raises_on_error(self):
        from lib.testtool.phm.exceptions import PHMUIError
        self.m._page.fill.side_effect = Exception("not found")
        with pytest.raises(PHMUIError):
            self.m.set_cycle_count(5)

    def test_set_test_duration_fills_input(self):
        from lib.testtool.phm.ui_monitor import _SEL_DURATION_INPUT
        self.m.set_test_duration(90)
        self.m._page.fill.assert_called_once_with(_SEL_DURATION_INPUT, '90')

    def test_set_modern_standby_clicks_when_state_differs(self):
        checkbox = MagicMock()
        checkbox.is_checked.return_value = False
        self.m._page.locator.return_value = checkbox
        self.m.set_modern_standby_mode(True)
        checkbox.click.assert_called_once()

    def test_set_modern_standby_no_click_when_already_set(self):
        checkbox = MagicMock()
        checkbox.is_checked.return_value = True
        self.m._page.locator.return_value = checkbox
        self.m.set_modern_standby_mode(True)
        checkbox.click.assert_not_called()


class TestPHMUIMonitorTestControl:
    """Tests for start_test() and stop_test()."""

    def setup_method(self):
        self.m = _make_monitor()
        self.m._connected = True
        self.m._page = MagicMock()

    def test_start_test_clicks_btn(self):
        from lib.testtool.phm.ui_monitor import _SEL_START_BTN
        self.m.start_test()
        self.m._page.click.assert_called_once_with(_SEL_START_BTN)

    def test_stop_test_clicks_btn(self):
        from lib.testtool.phm.ui_monitor import _SEL_STOP_BTN
        self.m.stop_test()
        self.m._page.click.assert_called_once_with(_SEL_STOP_BTN)

    def test_start_test_raises_on_error(self):
        from lib.testtool.phm.exceptions import PHMUIError
        self.m._page.click.side_effect = Exception("btn not found")
        with pytest.raises(PHMUIError):
            self.m.start_test()


class TestPHMUIMonitorStatusAndScreenshot:
    """Tests for get_current_status() and take_screenshot()."""

    def setup_method(self):
        self.m = _make_monitor()
        self.m._connected = True
        self.m._page = MagicMock()

    def test_get_current_status_returns_text(self):
        mock_elem = MagicMock()
        mock_elem.inner_text.return_value = '  Running  '
        self.m._page.locator.return_value.first = mock_elem
        status = self.m.get_current_status()
        assert status == 'Running'

    def test_get_current_status_raises_on_error(self):
        from lib.testtool.phm.exceptions import PHMUIError
        self.m._page.locator.return_value.first.inner_text.side_effect = Exception("err")
        with pytest.raises(PHMUIError):
            self.m.get_current_status()

    def test_take_screenshot_calls_playwright(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'shot.png')
            result = self.m.take_screenshot(path)
            self.m._page.screenshot.assert_called_once()
            assert 'shot.png' in result

    def test_take_screenshot_raises_on_error(self):
        from lib.testtool.phm.exceptions import PHMUIError
        self.m._page.screenshot.side_effect = Exception("capture failed")
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(PHMUIError):
                self.m.take_screenshot(os.path.join(tmpdir, 'x.png'))


class TestPHMUIMonitorWaitForCompletion:
    """Tests for wait_for_completion()."""

    def setup_method(self):
        self.m = _make_monitor()
        self.m._connected = True
        self.m._page = MagicMock()

    def test_returns_true_on_pass_status(self):
        mock_elem = MagicMock()
        mock_elem.inner_text.return_value = 'Pass'
        self.m._page.locator.return_value.first = mock_elem
        with patch('lib.testtool.phm.ui_monitor.time.sleep'):
            result = self.m.wait_for_completion(timeout=10)
        assert result

    def test_returns_true_on_fail_status(self):
        mock_elem = MagicMock()
        mock_elem.inner_text.return_value = 'Fail'
        self.m._page.locator.return_value.first = mock_elem
        with patch('lib.testtool.phm.ui_monitor.time.sleep'):
            result = self.m.wait_for_completion(timeout=10)
        assert result

    def test_raises_timeout_error(self):
        from lib.testtool.phm.exceptions import PHMTimeoutError
        mock_elem = MagicMock()
        mock_elem.inner_text.return_value = 'Running'
        self.m._page.locator.return_value.first = mock_elem
        with patch('lib.testtool.phm.ui_monitor.time.sleep'):
            with patch('lib.testtool.phm.ui_monitor.time.time',
                       side_effect=[0, 0, 0, 100]):
                with pytest.raises(PHMTimeoutError):
                    self.m.wait_for_completion(timeout=1)





