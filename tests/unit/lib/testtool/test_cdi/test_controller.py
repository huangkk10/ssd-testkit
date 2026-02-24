"""
Unit tests for CDI Controller.
Tests CDIController and CDILogParser with mocked dependencies.
"""

import json
import os
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

from lib.testtool.cdi.controller import CDIController, CDILogParser
from lib.testtool.cdi.exceptions import (
    CDIConfigError,
    CDIError,
    CDIProcessError,
    CDITestFailedError,
    CDITimeoutError,
)


# ---------------------------------------------------------------------------
# CDIController tests
# ---------------------------------------------------------------------------

class TestCDIController(unittest.TestCase):

    def setUp(self):
        self.valid_kwargs = {
            'executable_path': './bin/CrystalDiskInfo/DiskInfo64.exe',
            'log_path': './testlog',
            'timeout_seconds': 60,
        }
        self._patch_exists = patch('pathlib.Path.exists', return_value=True)
        self._patch_mkdir = patch('pathlib.Path.mkdir')
        self._patch_exists.start()
        self._patch_mkdir.start()

    def tearDown(self):
        self._patch_exists.stop()
        self._patch_mkdir.stop()

    # ----- Initialization -----

    def test_init_sets_defaults(self):
        ctrl = CDIController(**self.valid_kwargs)
        self.assertEqual(ctrl._config['timeout_seconds'], 60)
        self.assertIsNone(ctrl.status)
        self.assertEqual(ctrl.error_count, 0)

    def test_is_thread(self):
        ctrl = CDIController(**self.valid_kwargs)
        self.assertIsInstance(ctrl, threading.Thread)

    def test_daemon_thread(self):
        ctrl = CDIController(**self.valid_kwargs)
        self.assertTrue(ctrl.daemon)

    def test_init_invalid_config_raises(self):
        with self.assertRaises(CDIConfigError):
            CDIController(unknown_param='bad')

    # ----- set_config -----

    def test_set_config_updates_value(self):
        ctrl = CDIController(**self.valid_kwargs)
        ctrl.set_config(timeout_seconds=120)
        self.assertEqual(ctrl._config['timeout_seconds'], 120)

    def test_set_config_invalid_key_raises(self):
        ctrl = CDIController(**self.valid_kwargs)
        with self.assertRaises(CDIConfigError):
            ctrl.set_config(bad_key='value')

    # ----- status property -----

    def test_status_initially_none(self):
        ctrl = CDIController(**self.valid_kwargs)
        self.assertIsNone(ctrl.status)

    # ----- error_count -----

    def test_error_count_initially_zero(self):
        ctrl = CDIController(**self.valid_kwargs)
        self.assertEqual(ctrl.error_count, 0)

    # ----- stop -----

    def test_stop_sets_event(self):
        ctrl = CDIController(**self.valid_kwargs)
        self.assertFalse(ctrl._stop_event.is_set())
        ctrl.stop()
        self.assertTrue(ctrl._stop_event.is_set())

    # ----- run (mocked _execute_workflow) -----

    @patch.object(CDIController, '_execute_workflow')
    def test_run_sets_status_true_on_success(self, mock_workflow):
        mock_workflow.return_value = None
        ctrl = CDIController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertTrue(ctrl.status)

    @patch.object(CDIController, '_execute_workflow')
    def test_run_sets_status_false_on_timeout(self, mock_workflow):
        mock_workflow.side_effect = CDITimeoutError('timed out')
        ctrl = CDIController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)

    @patch.object(CDIController, '_execute_workflow')
    def test_run_sets_status_false_on_cdi_error(self, mock_workflow):
        mock_workflow.side_effect = CDIError('generic error')
        ctrl = CDIController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)

    @patch.object(CDIController, '_execute_workflow')
    def test_run_sets_status_false_on_unexpected_error(self, mock_workflow):
        mock_workflow.side_effect = RuntimeError('unexpected')
        ctrl = CDIController(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)

    # ----- kill_processes (static) -----

    @patch('lib.testtool.cdi.controller.psutil.process_iter')
    @patch('lib.testtool.cdi.controller.subprocess.call')
    def test_kill_processes_calls_taskkill(self, mock_call, mock_iter):
        proc = Mock()
        proc.info = {'name': 'DiskInfo64.exe'}
        mock_iter.return_value = [proc]
        CDIController.kill_processes(['DiskInfo64.exe'])
        mock_call.assert_called_once()

    @patch('lib.testtool.cdi.controller.psutil.process_iter')
    @patch('lib.testtool.cdi.controller.subprocess.call')
    def test_kill_processes_skips_non_matching(self, mock_call, mock_iter):
        proc = Mock()
        proc.info = {'name': 'notepad.exe'}
        mock_iter.return_value = [proc]
        CDIController.kill_processes(['DiskInfo64.exe'])
        mock_call.assert_not_called()

    # ----- SMART helpers -----

    def _write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f)

    def test_get_drive_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl = CDIController(log_path=tmpdir, executable_path='./x.exe')
            json_path = os.path.join(tmpdir, 'DiskInfo.json')
            self._write_json(json_path, {
                'disks': [{'Model': 'SSD Pro', 'Drive Letter': 'C:', 'DiskNum': '1'}]
            })
            ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
            result = ctrl.get_drive_info('C:', '', 'Model')
            self.assertEqual(result, 'SSD Pro')

    def test_get_drive_info_missing_drive_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl = CDIController(log_path=tmpdir, executable_path='./x.exe')
            json_path = os.path.join(tmpdir, 'DiskInfo.json')
            self._write_json(json_path, {'disks': []})
            ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
            with self.assertRaises(CDIError):
                ctrl.get_drive_info('Z:', '', 'Model')

    def test_get_smart_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl = CDIController(log_path=tmpdir, executable_path='./x.exe')
            json_path = os.path.join(tmpdir, 'DiskInfo.json')
            self._write_json(json_path, {
                'disks': [{
                    'Drive Letter': 'C:',
                    'S.M.A.R.T.': [
                        {'RawValues': '000000000005', 'Attribute Name': 'Power Cycles'},
                    ],
                }]
            })
            ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
            values = ctrl.get_smart_value('C:', '', ['Power Cycles'])
            self.assertEqual(values[0]['Power Cycles'], 5)

    def test_compare_smart_value_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl = CDIController(log_path=tmpdir, executable_path='./x.exe')
            json_path = os.path.join(tmpdir, 'DiskInfo.json')
            self._write_json(json_path, {
                'disks': [{
                    'Drive Letter': 'C:',
                    'S.M.A.R.T.': [
                        {'RawValues': '000000000000', 'Attribute Name': 'Unsafe Shutdowns'},
                    ],
                }]
            })
            ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
            ok, msg = ctrl.compare_smart_value('C:', '', ['Unsafe Shutdowns'], 0)
            self.assertTrue(ok)
            self.assertIn('Passed', msg)

    def test_compare_smart_value_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl = CDIController(log_path=tmpdir, executable_path='./x.exe')
            json_path = os.path.join(tmpdir, 'DiskInfo.json')
            self._write_json(json_path, {
                'disks': [{
                    'Drive Letter': 'C:',
                    'S.M.A.R.T.': [
                        {'RawValues': '000000000003', 'Attribute Name': 'Unsafe Shutdowns'},
                    ],
                }]
            })
            ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
            ok, msg = ctrl.compare_smart_value('C:', '', ['Unsafe Shutdowns'], 0)
            self.assertFalse(ok)
            self.assertIn('Failed', msg)

    def test_compare_smart_value_no_increase_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl = CDIController(log_path=tmpdir, executable_path='./x.exe')

            before_path = os.path.join(tmpdir, 'Before_DiskInfo.json')
            after_path = os.path.join(tmpdir, 'After_DiskInfo.json')
            smart = [{'RawValues': '000000000005', 'Attribute Name': 'Power Cycles'}]
            disk = {'Drive Letter': 'C:', 'S.M.A.R.T.': smart}
            self._write_json(before_path, {'disks': [disk]})
            self._write_json(after_path,  {'disks': [disk]})

            ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
            ok, msg = ctrl.compare_smart_value_no_increase('C:', 'Before_', 'After_', ['Power Cycles'])
            self.assertTrue(ok)

    def test_compare_smart_value_increase_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl = CDIController(log_path=tmpdir, executable_path='./x.exe')

            before_path = os.path.join(tmpdir, 'Before_DiskInfo.json')
            after_path = os.path.join(tmpdir, 'After_DiskInfo.json')
            before_disk = {'Drive Letter': 'C:', 'S.M.A.R.T.': [
                {'RawValues': '000000000001', 'Attribute Name': 'Power Cycles'}
            ]}
            after_disk = {'Drive Letter': 'C:', 'S.M.A.R.T.': [
                {'RawValues': '00000000000E', 'Attribute Name': 'Power Cycles'}  # +13
            ]}
            self._write_json(before_path, {'disks': [before_disk]})
            self._write_json(after_path,  {'disks': [after_disk]})

            ctrl._config['diskinfo_json_name'] = 'DiskInfo.json'
            ok, msg = ctrl.compare_smart_value_increase('C:', 'Before_', 'After_', 13, ['Power Cycles'])
            self.assertTrue(ok)


# ---------------------------------------------------------------------------
# CDILogParser tests
# ---------------------------------------------------------------------------

class TestCDILogParser(unittest.TestCase):

    def _write_txt(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    SAMPLE_TXT = (
        'CrystalDiskInfo 9.0.0 (C) 2008-2024 hiyohiyo\n'
        '    OS : Windows 11 Pro\n'
        '-- Controller Map\n'
        ' + Standard NVM Express Controller\n'
        '   - Samsung SSD 980 PRO\n'
        '-- Disk List\n'
        ' (1) Samsung SSD 980 PRO : 1000.2 GB [0/0/0, pd1]\n'
        '-----------------\n'
        ' (1) Samsung SSD 980 PRO\n'
        ' Model : Samsung SSD 980 PRO\n'
        ' Drive Letter : C:\n'
        '-- S.M.A.R.T. Samsung SSD 980 PRO\n'
        '01 000000000005 Power Cycles\n'
    )

    def test_parse_file_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt = os.path.join(tmpdir, 'DiskInfo.txt')
            self._write_txt(txt, self.SAMPLE_TXT)
            parser = CDILogParser()
            result = parser.parse_file(txt)
            self.assertIsInstance(result, dict)

    def test_parse_cdi_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt = os.path.join(tmpdir, 'DiskInfo.txt')
            self._write_txt(txt, self.SAMPLE_TXT)
            result = CDILogParser().parse_file(txt)
            self.assertEqual(result['CDI']['version'], '9.0.0')

    def test_parse_os_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt = os.path.join(tmpdir, 'DiskInfo.txt')
            self._write_txt(txt, self.SAMPLE_TXT)
            result = CDILogParser().parse_file(txt)
            self.assertIn('Windows 11', result['OS']['version'])

    def test_parse_controller_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt = os.path.join(tmpdir, 'DiskInfo.txt')
            self._write_txt(txt, self.SAMPLE_TXT)
            result = CDILogParser().parse_file(txt)
            self.assertIn('Standard NVM Express Controller', result['controllers_disks'])

    def test_parse_disk_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt = os.path.join(tmpdir, 'DiskInfo.txt')
            self._write_txt(txt, self.SAMPLE_TXT)
            result = CDILogParser().parse_file(txt)
            self.assertGreaterEqual(len(result['disks']), 1)

    def test_parse_smart_attribute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt = os.path.join(tmpdir, 'DiskInfo.txt')
            self._write_txt(txt, self.SAMPLE_TXT)
            result = CDILogParser().parse_file(txt)
            smart = result['disks'][0].get('S.M.A.R.T.', [])
            attr_names = [s['Attribute Name'] for s in smart]
            self.assertIn('Power Cycles', attr_names)

    def test_parse_writes_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt = os.path.join(tmpdir, 'DiskInfo.txt')
            json_out = os.path.join(tmpdir, 'DiskInfo.json')
            self._write_txt(txt, self.SAMPLE_TXT)
            CDILogParser().parse_file(txt, json_output_path=json_out)
            self.assertTrue(os.path.exists(json_out))
            with open(json_out) as f:
                data = json.load(f)
            self.assertIn('CDI', data)

    def test_parse_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            CDILogParser().parse_file('/nonexistent/DiskInfo.txt')


if __name__ == '__main__':
    unittest.main()
