"""
CDI (CrystalDiskInfo) Controller

Threading-based controller for managing CrystalDiskInfo execution.
Orchestrates: kill stale process → open UI → export text log → parse to
JSON → capture screenshots → close.  Also provides SMART data query and
comparison helpers.
"""

import threading
import enum
import json
import os
import re
import subprocess
import time
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import psutil

from lib.logger import get_module_logger
from .config import CDIConfig
from .exceptions import (
    CDIError,
    CDIConfigError,
    CDIProcessError,
    CDITestFailedError,
    CDITimeoutError,
    CDIUIError,
)
from .ui_monitor import CDIUIMonitor

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# ReadMode enum  (used by CDILogParser)
# ---------------------------------------------------------------------------

class ReadMode(enum.Enum):
    """State machine modes for parsing the CrystalDiskInfo text report."""
    start = 1
    cdiversion = 2
    controllermap = 3
    disklist = 4
    drivedata = 5
    smartdata = 6
    identifydata = 7
    smartreaddata = 8
    smartreadthreshold = 9


# ---------------------------------------------------------------------------
# CDILogParser
# ---------------------------------------------------------------------------

class CDILogParser:
    """
    Parses a CrystalDiskInfo plain-text report (DiskInfo.txt) into a
    structured Python dictionary and optionally writes it to JSON.

    Example:
        >>> parser = CDILogParser()
        >>> data = parser.parse_file('./testlog/DiskInfo.txt')
        >>> data['disks'][0]['Model']
        'Samsung SSD 980 PRO 1TB'
    """

    def parse_file(self, txt_path: str, json_output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse a DiskInfo.txt file.

        Args:
            txt_path:         Path to the DiskInfo.txt source file.
            json_output_path: If provided, write the parsed dict to this JSON file.

        Returns:
            Parsed data dict with keys: CDI, OS, controllers_disks, disks.

        Raises:
            FileNotFoundError: If txt_path does not exist.
            CDIError: On unexpected parse failure.
        """
        with open(txt_path, newline='') as f:
            input_data = f.read()

        data = self._parse_text(input_data)

        if json_output_path:
            os.makedirs(os.path.dirname(os.path.abspath(json_output_path)), exist_ok=True)
            with open(json_output_path, 'w') as f:
                f.write(json.dumps(data, indent=4, separators=(',', ': '), sort_keys=True))
            logger.info(f"CDILogParser: JSON written to {json_output_path}")

        return data

    def _parse_text(self, input_data: str) -> Dict[str, Any]:
        """Parse the raw text content of DiskInfo.txt."""
        obj: Dict[str, Any] = {
            'CDI': {},
            'OS': {},
            'controllers_disks': {},
            'disks': [],
        }
        curmode = ReadMode.start
        curdiskidx: Optional[str] = None
        cur_controller: Optional[str] = None

        for line in input_data.splitlines():
            # Skip blank lines
            if not line:
                continue

            # --- Mode pivots ---
            if re.search(r'^-- Controller Map', line):
                curmode = ReadMode.controllermap
                continue
            if re.search(r'^-- Disk List', line):
                curmode = ReadMode.disklist
                continue
            if re.search(r'^-- S\.M\.A\.R\.T\. ', line):
                curmode = ReadMode.smartdata
                continue
            if re.search(r'^-- IDENTIFY_DEVICE ', line):
                curmode = ReadMode.identifydata
                continue
            if re.search(r'^-- SMART_READ_DATA ', line):
                curmode = ReadMode.smartreaddata
                continue
            if re.search(r'^-- SMART_READ_THRESHOLD ', line):
                curmode = ReadMode.smartreadthreshold
                continue

            # --- Global header fields ---
            m = re.search(r'^CrystalDiskInfo (\d+\.\d+\.\d+)', line)
            if m:
                obj['CDI']['version'] = m.group(1)
                continue

            m = re.search(r'^    OS : (.*)$', line)
            if m:
                obj['OS']['version'] = m.group(1)
                continue

            # --- Controller map ---
            if curmode == ReadMode.controllermap:
                if line.startswith(' + '):
                    cur_controller = line[len(' + '):]
                    obj['controllers_disks'][cur_controller] = []
                elif line.startswith('   - ') and cur_controller:
                    obj['controllers_disks'][cur_controller].append(line[len('   - '):])
                continue

            # --- Disk list ---
            if curmode == ReadMode.disklist:
                m = re.search(r'^ \((\d+)\) (.*) : (.*) \[(.*)/\d+/.*$', line)
                if m:
                    idx, name, size, phyid = m.groups()
                    obj['disks'].append({
                        'DiskNum': idx,
                        'Model': name,
                        'Disk Size': size,
                        'Physical Drive ID': phyid,
                    })
                elif line.startswith('-----------------'):
                    curmode = ReadMode.drivedata
                continue

            # --- Drive header "(N) DiskName" ---
            m = re.search(r'^ \((\d+)\) (.*)$', line)
            if m:
                curmode = ReadMode.drivedata
                curdiskidx, _ = m.groups()
                continue

            # --- Drive attribute key : value ---
            if curmode == ReadMode.drivedata:
                parts = [x.strip() for x in line.split(' : ')]
                if len(parts) >= 2:
                    key, value = parts[0], parts[1]
                    if curdiskidx is not None:
                        obj['disks'][int(curdiskidx) - 1][key] = value
                continue

            # --- S.M.A.R.T. data ---
            if curmode == ReadMode.smartdata and curdiskidx is not None:
                disk = obj['disks'][int(curdiskidx) - 1]
                if 'S.M.A.R.T.' not in disk:
                    disk['S.M.A.R.T.'] = []

                # SATA format
                m = re.search(
                    r'^([A-F0-9]{2}) _*(\d*) _*(\d*) _*(\d*) ([A-F0-9]{12}) (.*)$', line
                )
                if m:
                    _id, cur, wor, thr, rawvalues, attrname = m.groups()
                    disk['S.M.A.R.T.'].append({
                        'ID': _id, 'Cur': cur, 'Wor': wor,
                        'Thr': thr, 'RawValues': rawvalues, 'Attribute Name': attrname,
                    })
                    continue

                # NVMe format
                m = re.search(r'^([A-F0-9]{2}) ([A-F0-9]{12}) (.*)$', line)
                if m:
                    _id, rawvalues, attrname = m.groups()
                    disk['S.M.A.R.T.'].append({
                        'ID': _id, 'RawValues': rawvalues, 'Attribute Name': attrname,
                    })
                continue

            # --- Raw hex sections (IDENTIFY / SMART_READ_DATA / THRESHOLD) ---
            hex_section_map = {
                ReadMode.identifydata: 'IDENTIFY_DEVICE',
                ReadMode.smartreaddata: 'SMART_READ_DATA',
                ReadMode.smartreadthreshold: 'SMART_READ_THRESHOLD',
            }
            if curmode in hex_section_map and curdiskidx is not None:
                if line.startswith('    '):
                    continue  # skip header rows
                hexdata = ''.join(line.split(' ')[1:])
                disk = obj['disks'][int(curdiskidx) - 1]
                section = hex_section_map[curmode]
                if section not in disk:
                    disk[section] = ''
                disk[section] += hexdata
                continue

        return obj


# ---------------------------------------------------------------------------
# CDIController
# ---------------------------------------------------------------------------

class CDIController(threading.Thread):
    """
    Controller for CrystalDiskInfo (DiskInfo64.exe) test execution.

    Orchestrates the full monitoring workflow inside a daemon thread:
    kill any stale DiskInfo process → create log directory →
    launch CrystalDiskInfo → export text log → parse log to JSON →
    capture screenshots → close window.

    Also provides static SMART query and comparison helpers that operate
    on an already-written DiskInfo.json file.

    Example:
        >>> controller = CDIController(
        ...     executable_path='./bin/CrystalDiskInfo/DiskInfo64.exe',
        ...     log_path='./testlog',
        ...     screenshot_drive_letter='C:',
        ... )
        >>> controller.start()
        >>> controller.join(timeout=300)
        >>> assert controller.status is True
    """

    def __init__(self, **kwargs):
        super().__init__(daemon=True)
        self._config: Dict[str, Any] = CDIConfig.get_default_config()
        if kwargs:
            self._config = CDIConfig.merge_config(self._config, kwargs)

        self._stop_event = threading.Event()
        self._status: Optional[bool] = None
        self._error_count: int = 0
        self._log_parser = CDILogParser()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_config(self, **kwargs) -> None:
        """Update runtime configuration."""
        self._config = CDIConfig.merge_config(self._config, kwargs)

    def load_config_from_json(self, json_path: str, config_key: str = 'cdi') -> None:
        """
        Load CDI configuration from a Config.json file.

        Reads the specified key from the JSON file and maps the legacy
        CrystalDiskInfo field names to the CDIConfig parameter names:

        +------------------------+-----------------------------+
        | Config.json key        | CDIConfig key               |
        +------------------------+-----------------------------+
        | ExePath                | executable_path             |
        | LogPath                | log_path                    |
        | LogPrefix              | log_prefix                  |
        | ScreenShotDriveLetter  | screenshot_drive_letter     |
        +------------------------+-----------------------------+

        Unknown or unmapped keys are silently skipped.

        Args:
            json_path:  Path to the JSON configuration file.
            config_key: Top-level key that contains the CDI section
                        (default: 'cdi').

        Raises:
            CDIConfigError: If the file is missing, not valid JSON, or the
                            config_key is absent.

        Example:
            >>> controller = CDIController()
            >>> controller.load_config_from_json('./Config/Config.json')
            >>> controller.start()
        """
        # Legacy key → CDIConfig key mapping
        _KEY_MAP: Dict[str, str] = {
            'ExePath':               'executable_path',
            'LogPath':               'log_path',
            'LogPrefix':             'log_prefix',
            'ScreenShotDriveLetter': 'screenshot_drive_letter',
        }

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CDIConfigError(f"Config file not found: {json_path}")
        except json.JSONDecodeError as exc:
            raise CDIConfigError(f"Invalid JSON in {json_path}: {exc}")

        if config_key not in data:
            raise CDIConfigError(
                f"Key '{config_key}' not found in {json_path}"
            )

        raw = data[config_key]

        # Resolve testlog path for packaged environments
        try:
            from path_manager import path_manager
            testlog_dir = str(path_manager.get_testlog_dir())
        except ImportError:
            testlog_dir = './testlog'

        mapped: Dict[str, Any] = {}
        for raw_key, value in raw.items():
            cdi_key = _KEY_MAP.get(raw_key, raw_key)  # fall back to same name
            if cdi_key not in CDIConfig.VALID_PARAMS:
                logger.debug(f"CDIController.load_config_from_json: skipping unknown key '{raw_key}'")
                continue
            if isinstance(value, str) and './testlog' in value:
                value = value.replace('./testlog', testlog_dir)
            mapped[cdi_key] = value

        self.set_config(**mapped)
        logger.info(f"CDIController: config loaded from {json_path} (key='{config_key}')")
        logger.debug(f"CDIController: applied config: {mapped}")

    @property
    def status(self) -> Optional[bool]:
        """
        Execution status.
        Returns None while running, True on pass, False on fail.
        """
        return self._status

    @property
    def error_count(self) -> int:
        """Number of errors detected during execution."""
        return self._error_count

    def stop(self) -> None:
        """Signal the controller to stop."""
        logger.info("CDIController: stop signal received")
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Thread body
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Thread body: execute the full CDI workflow."""
        logger.info("CDIController: starting CDI workflow")
        try:
            self._execute_workflow()
            self._status = True
            logger.info("CDIController: workflow completed successfully")
        except CDITestFailedError as e:
            logger.error(f"CDIController: test failed: {e}")
            self._status = False
        except CDITimeoutError as e:
            logger.error(f"CDIController: timeout: {e}")
            self._status = False
        except CDIError as e:
            logger.error(f"CDIController: CDI error: {e}")
            self._status = False
        except Exception as e:
            logger.error(f"CDIController: unexpected error: {e}", exc_info=True)
            self._status = False

    # ------------------------------------------------------------------
    # Workflow steps
    # ------------------------------------------------------------------

    def _execute_workflow(self) -> None:
        """Run the complete monitoring sequence."""
        cfg = self._config
        log_path = cfg['log_path']
        prefix = cfg['log_prefix']
        exe_path = cfg['executable_path']

        txt_name = cfg['diskinfo_txt_name']
        json_name = cfg['diskinfo_json_name']
        png_name = cfg['diskinfo_png_name']
        drive_letter = cfg['screenshot_drive_letter']

        txt_path = os.path.abspath(f"{log_path}/{prefix}{txt_name}")
        json_path = os.path.abspath(f"{log_path}/{prefix}{json_name}")

        # 1. Kill stale process
        logger.info("CDIController: killing stale DiskInfo64.exe processes")
        self.kill_processes(['DiskInfo64.exe'])

        # 2. Create log directory
        logger.info(f"CDIController: creating log directory: {log_path}")
        Path(log_path).mkdir(parents=True, exist_ok=True)

        # 3. Open CDI
        monitor = CDIUIMonitor(
            window_title=cfg['window_title'],
            window_class=cfg['window_class'],
            save_dialog_timeout=cfg['save_dialog_timeout'],
            save_retry_max=cfg['save_retry_max'],
        )
        logger.info("CDIController: opening CrystalDiskInfo")
        monitor.open(exe_path)

        try:
            # 4. Export text log
            logger.info("CDIController: exporting text log")
            monitor.get_text_log(txt_path)

            # 5. Parse to JSON
            logger.info("CDIController: parsing text log to JSON")
            self._log_parser.parse_file(txt_path, json_output_path=json_path)

            # 6. Screenshot (optional)
            if drive_letter or True:  # always attempt; drive_letter='' = all drives
                logger.info("CDIController: capturing screenshots")
                monitor.get_screenshot(
                    log_dir=log_path,
                    prefix=prefix,
                    drive_letter=drive_letter,
                    diskinfo_json_path=json_path,
                    png_name_override=png_name,
                )
        finally:
            # 7. Close window
            logger.info("CDIController: closing CrystalDiskInfo")
            monitor.close()

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------

    @staticmethod
    def kill_processes(process_names: List[str]) -> None:
        """
        Force-kill Windows processes by name.

        Args:
            process_names: List of executable names (e.g. ['DiskInfo64.exe']).
        """
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in process_names:
                logger.info(f"CDIController: taskkill {proc.info['name']}")
                subprocess.call(['taskkill', '/F', '/IM', proc.info['name']])

    # ------------------------------------------------------------------
    # SMART helpers  (operate on an already-written DiskInfo.json)
    # ------------------------------------------------------------------

    def get_drive_info(
        self,
        drive_letter: str,
        log_prefix: str,
        key: str,
    ) -> str:
        """
        Read a single attribute for a disk from the DiskInfo JSON.

        Args:
            drive_letter: Drive letter (e.g. 'C:').
            log_prefix:   Filename prefix used when the JSON was written.
            key:          Attribute name (e.g. 'Serial Number', 'DiskNum').

        Returns:
            Attribute value as a string.

        Example:
            >>> sn = controller.get_drive_info('C:', '', 'Serial Number')
        """
        json_path = os.path.abspath(
            f"{self._config['log_path']}/{log_prefix}{self._config['diskinfo_json_name']}"
        )
        with open(json_path, newline='') as f:
            data = json.load(f)
        disks = data.get('disks', [])
        matches = [d for d in disks if drive_letter in d.get('Drive Letter', '')]
        if not matches:
            raise CDIError(f"Drive '{drive_letter}' not found in {json_path}")
        return str(matches[0][key])

    def get_smart_value(
        self,
        drive_letter: str,
        log_prefix: str,
        keys: List[str],
    ) -> List[Dict[str, int]]:
        """
        Retrieve SMART attribute raw values (as integers) for a drive.

        Args:
            drive_letter: Drive letter (e.g. 'C:').
            log_prefix:   Filename prefix of the JSON to read.
            keys:         SMART attribute names to retrieve
                          (e.g. ['Power Cycles', 'Power On Hours']).

        Returns:
            A list containing one dict mapping attribute name → raw value (int).

        Example:
            >>> values = controller.get_smart_value('C:', '', ['Power Cycles'])
            >>> values[0]['Power Cycles']
            5
        """
        json_path = os.path.abspath(
            f"{self._config['log_path']}/{log_prefix}{self._config['diskinfo_json_name']}"
        )
        with open(json_path, newline='') as f:
            data = json.load(f)
        disks = data.get('disks', [])
        matches = [d for d in disks if drive_letter in d.get('Drive Letter', '')]
        if not matches:
            raise CDIError(f"Drive '{drive_letter}' not found in {json_path}")
        smart = matches[0].get('S.M.A.R.T.', [])
        result: Dict[str, int] = {}
        for key in keys:
            attrs = [x for x in smart if x.get('Attribute Name') == key]
            if attrs:
                result[key] = int(attrs[0]['RawValues'], 16)
        return [result]

    def compare_smart_value(
        self,
        drive_letter: str,
        log_prefix: str,
        keys: List[str],
        expected_value: int,
    ) -> Tuple[bool, str]:
        """
        Assert that each listed SMART attribute equals *expected_value*.

        Args:
            drive_letter:   Drive letter.
            log_prefix:     JSON filename prefix.
            keys:           SMART attribute names to check.
            expected_value: Expected integer value.

        Returns:
            (True, message) on pass; (False, message) on fail.

        Example:
            >>> ok, msg = controller.compare_smart_value('C:', '', ['Media and Data Integrity Errors'], 0)
            >>> if not ok:
            ...     raise Exception(msg)
        """
        values = self.get_smart_value(drive_letter, log_prefix, keys)
        for key in keys:
            got = values[0].get(key)
            if got != expected_value:
                msg = f'Check SMART Failed {key}: {got} != {expected_value}'
                logger.error(msg)
                return False, msg
            msg = f'Check SMART Passed {key}: {got} == {expected_value}'
            logger.info(msg)
        return True, msg

    def compare_smart_value_no_increase(
        self,
        drive_letter: str,
        before_prefix: str,
        after_prefix: str,
        keys: List[str],
    ) -> Tuple[bool, str]:
        """
        Assert that SMART attributes did not increase between two snapshots.

        Args:
            drive_letter:  Drive letter.
            before_prefix: Log prefix of the before-snapshot JSON.
            after_prefix:  Log prefix of the after-snapshot JSON.
            keys:          SMART attribute names to compare.

        Returns:
            (True, message) on pass; (False, message) on fail.

        Example:
            >>> ok, msg = controller.compare_smart_value_no_increase(
            ...     'C:', 'Before_', 'After_', ['Unsafe Shutdowns'])
            >>> if not ok:
            ...     raise Exception(msg)
        """
        before = self.get_smart_value(drive_letter, before_prefix, keys)
        after = self.get_smart_value(drive_letter, after_prefix, keys)
        msg = ''
        for key in keys:
            bf = before[0].get(key, 0)
            af = after[0].get(key, 0)
            if bf != af:
                msg = f'Check SMART Failed {key}: {bf} != {af}'
                logger.error(msg)
                return False, msg
            msg = f'Check SMART Passed {key}: {bf} == {af}'
            logger.info(msg)
        return True, msg

    def compare_smart_value_increase(
        self,
        drive_letter: str,
        before_prefix: str,
        after_prefix: str,
        expected_delta: int,
        keys: List[str],
    ) -> Tuple[bool, str]:
        """
        Assert that SMART attributes increased by exactly *expected_delta*.

        Args:
            drive_letter:   Drive letter.
            before_prefix:  Log prefix of the before-snapshot JSON.
            after_prefix:   Log prefix of the after-snapshot JSON.
            expected_delta: Expected increase amount.
            keys:           SMART attribute names to compare.

        Returns:
            (True, message) on pass; (False, message) on fail.

        Example:
            >>> ok, msg = controller.compare_smart_value_increase(
            ...     'C:', 'Before_', 'After_', 13, ['Power Cycles'])
            >>> if not ok:
            ...     raise Exception(msg)
        """
        before = self.get_smart_value(drive_letter, before_prefix, keys)
        after = self.get_smart_value(drive_letter, after_prefix, keys)
        msg = ''
        for key in keys:
            bf = before[0].get(key, 0)
            af = after[0].get(key, 0)
            delta = af - bf
            if delta != expected_delta:
                msg = f'Check SMART Failed {key}: {af} - {bf} = {delta} != {expected_delta}'
                logger.error(msg)
                return False, msg
            msg = f'Check SMART Passed {key}: {af} - {bf} = {delta} == {expected_delta}'
            logger.info(msg)
        return True, msg
