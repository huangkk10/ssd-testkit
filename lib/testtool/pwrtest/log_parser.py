"""
PwrTest Log Parser

Parses the text log file (pwrtestlog.log) and XML file (pwrtestlog.xml)
produced by pwrtest.exe after a sleep/resume test run.

Log format sample (pwrtestlog.log):
    Start: PwrTest
    ...
    No.1 of 1 Transition -- TargetState: S3
      TargetState:       S3
      EffectiveState:    S3
      SleepTimeMs:       1134
      BiosInitTimeMs:    3242
      DriverWakeTimeMs:  442
      Transition StartTime: 03/02/2026 12:57:38::597
      Transition EndTime:   03/02/2026 12:58:43::956
    No.1 of 1 Transition -- Complete
    End: Pass, PwrTest, (null)
"""

import re
import os
import glob
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from xml.etree import ElementTree as ET

from .exceptions import PwrTestLogParseError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Regex patterns for pwrtestlog.log text format
# ---------------------------------------------------------------------------

_RE_END_PASS     = re.compile(r'End:\s*Pass', re.IGNORECASE)
_RE_END_FAIL     = re.compile(r'End:\s*Fail', re.IGNORECASE)
_RE_TRANS_HEADER = re.compile(
    r'No\.(\d+)\s+of\s+(\d+)\s+Transition\s+--\s+TargetState:\s*(\S+)'
)
_RE_TRANS_COMPLETE = re.compile(
    r'No\.\d+\s+of\s+\d+\s+Transition\s+--\s+Complete'
)
_RE_SLEEP_TIME    = re.compile(r'SleepTimeMs\s*:\s*(\d+)')
_RE_BIOS_INIT     = re.compile(r'BiosInitTimeMs\s*:\s*(\d+)')
_RE_DRIVER_WAKE   = re.compile(r'DriverWakeTimeMs\s*:\s*(\d+)')
_RE_TRANS_START   = re.compile(r'Transition StartTime:\s*(.+)')
_RE_TRANS_END     = re.compile(r'Transition EndTime:\s*(.+)')
_RE_TARGET_STATE  = re.compile(r'TargetState\s*:\s*(\S+)')
_RE_EFFECTIVE_STATE = re.compile(r'EffectiveState\s*:\s*(\S+)')


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PwrTestTransitionResult:
    """
    Per-cycle sleep/resume transition data.

    Attributes:
        transition_number:   1-based index of this transition.
        total_transitions:   Total number of transitions configured (/c value).
        target_state:        Requested sleep state (e.g. ``"S3"``).
        effective_state:     Actual sleep state achieved.
        sleep_time_ms:       Time spent in sleep (milliseconds).
        bios_init_time_ms:   BIOS/firmware initialisation time on wake (ms).
        driver_wake_time_ms: Driver wake initialisation time (ms).
        start_time:          Transition start timestamp string.
        end_time:            Transition end timestamp string.
        completed:           Whether this transition reached *Complete* state.
    """
    transition_number:   int = 0
    total_transitions:   int = 0
    target_state:        str = ''
    effective_state:     str = ''
    sleep_time_ms:       Optional[int] = None
    bios_init_time_ms:   Optional[int] = None
    driver_wake_time_ms: Optional[int] = None
    start_time:          str = ''
    end_time:            str = ''
    completed:           bool = False


@dataclass
class PwrTestTestResult:
    """
    Aggregated result from a single pwrtestlog.log or pwrtestlog.xml file.

    Attributes:
        status:            ``"PASS"``, ``"FAIL"``, or ``"UNKNOWN"``.
        total_cycles:      Number of cycles configured (/c value).
        completed_cycles:  Number of transitions that reached *Complete*.
        transitions:       Per-cycle :class:`PwrTestTransitionResult` list.
        errors:            Error strings extracted from the log.
        raw_report_path:   Absolute path to the source file.
    """
    status:           str = 'UNKNOWN'
    total_cycles:     int = 0
    completed_cycles: int = 0
    transitions:      List[PwrTestTransitionResult] = field(default_factory=list)
    errors:           List[str] = field(default_factory=list)
    raw_report_path:  str = ''


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class PwrTestLogParser:
    """
    Parser for pwrtest.exe output files.

    Supports:
    - ``parse_log(path)``  — text format ``pwrtestlog.log``
    - ``parse_xml(path)``  — XML format  ``pwrtestlog.xml``
    - ``parse_report(path)``    — auto-detect by extension
    - ``parse_reports_batch(directory)``  — glob all supported files in a dir
    - ``summarize(results)`` — aggregate a list of :class:`PwrTestTestResult`

    Example::

        parser = PwrTestLogParser()
        result = parser.parse_log('./testlog/PwrTestLog/pwrtestlog.log')
        if result.status == 'PASS':
            print(f"Sleep test passed in {result.completed_cycles} cycle(s).")
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def parse_report(self, path: str) -> 'PwrTestTestResult':
        """
        Auto-detect file format and parse the report.

        Args:
            path: Path to ``pwrtestlog.log`` or ``pwrtestlog.xml``.

        Returns:
            :class:`PwrTestTestResult`

        Raises:
            PwrTestLogParseError: File not found, empty, or unsupported extension.
        """
        p = Path(path)
        if not p.exists():
            raise PwrTestLogParseError(
                f"Log file not found: '{path}'"
            )
        if p.stat().st_size == 0:
            raise PwrTestLogParseError(
                f"Log file is empty: '{path}'"
            )
        ext = p.suffix.lower()
        if ext == '.xml':
            return self.parse_xml(path)
        if ext == '.log' or ext == '.txt':
            return self.parse_log(path)
        raise PwrTestLogParseError(
            f"Unsupported log file extension '{ext}' for '{path}'. "
            "Expected .log or .xml"
        )

    def parse_log(self, path: str) -> 'PwrTestTestResult':
        """
        Parse a ``pwrtestlog.log`` text file.

        Args:
            path: Path to the log file.

        Returns:
            :class:`PwrTestTestResult`

        Raises:
            PwrTestLogParseError: File not found or empty.
        """
        p = Path(path)
        if not p.exists():
            raise PwrTestLogParseError(f"Log file not found: '{path}'")
        content = p.read_text(encoding='utf-8', errors='replace')
        if not content.strip():
            raise PwrTestLogParseError(f"Log file is empty: '{path}'")

        result = PwrTestTestResult(raw_report_path=str(p.resolve()))
        self._parse_log_text(content, result)
        logger.info(
            f"PwrTestLogParser: parsed '{path}' → status={result.status}, "
            f"cycles={result.completed_cycles}/{result.total_cycles}"
        )
        return result

    def parse_xml(self, path: str) -> 'PwrTestTestResult':
        """
        Parse a ``pwrtestlog.xml`` file.

        Args:
            path: Path to the XML file.

        Returns:
            :class:`PwrTestTestResult`

        Raises:
            PwrTestLogParseError: File not found, empty, or malformed XML.
        """
        p = Path(path)
        if not p.exists():
            raise PwrTestLogParseError(f"XML log file not found: '{path}'")
        if p.stat().st_size == 0:
            raise PwrTestLogParseError(f"XML log file is empty: '{path}'")

        try:
            tree = ET.parse(str(p))
        except ET.ParseError as exc:
            raise PwrTestLogParseError(
                f"Malformed XML in '{path}': {exc}"
            ) from exc

        result = PwrTestTestResult(raw_report_path=str(p.resolve()))
        self._parse_xml_tree(tree.getroot(), result)
        logger.info(
            f"PwrTestLogParser: parsed XML '{path}' → status={result.status}, "
            f"cycles={result.completed_cycles}/{result.total_cycles}"
        )
        return result

    def parse_reports_batch(
        self,
        directory: str,
        pattern: str = 'pwrtestlog.*',
    ) -> List['PwrTestTestResult']:
        """
        Parse all matching report files in a directory.

        Args:
            directory: Directory to scan.
            pattern:   Glob pattern relative to *directory* (default ``pwrtestlog.*``).

        Returns:
            List of :class:`PwrTestTestResult` objects (one per file found).

        Raises:
            PwrTestLogParseError: Directory does not exist.
        """
        d = Path(directory)
        if not d.exists():
            raise PwrTestLogParseError(
                f"Directory not found: '{directory}'"
            )
        matched = list(d.glob(pattern))
        if not matched:
            return []

        results = []
        for file_path in sorted(matched):
            if file_path.suffix.lower() not in ('.log', '.xml', '.txt'):
                continue
            try:
                results.append(self.parse_report(str(file_path)))
            except PwrTestLogParseError as exc:
                logger.warning(f"Skipping '{file_path}': {exc}")
        return results

    @staticmethod
    def summarize(results: List['PwrTestTestResult']) -> Dict[str, Any]:
        """
        Aggregate a list of results into a plain summary dict.

        Args:
            results: List of :class:`PwrTestTestResult`.

        Returns:
            Dict with keys: ``total``, ``pass``, ``fail``, ``unknown``,
            ``total_cycles``, ``completed_cycles``, ``error_summary``.
        """
        summary: Dict[str, Any] = {
            'total':            len(results),
            'pass':             0,
            'fail':             0,
            'unknown':          0,
            'total_cycles':     0,
            'completed_cycles': 0,
            'error_summary':    [],
        }
        for r in results:
            if r.status == 'PASS':
                summary['pass'] += 1
            elif r.status == 'FAIL':
                summary['fail'] += 1
            else:
                summary['unknown'] += 1
            summary['total_cycles']     += r.total_cycles
            summary['completed_cycles'] += r.completed_cycles
            summary['error_summary'].extend(r.errors)
        return summary

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _parse_log_text(self, content: str, result: 'PwrTestTestResult') -> None:
        """Parse plain-text pwrtestlog.log content into *result* (mutates it)."""
        lines = content.splitlines()

        current_transition: Optional[PwrTestTransitionResult] = None

        for line in lines:
            stripped = line.strip()

            # ---- Overall verdict ----
            if _RE_END_PASS.search(stripped):
                result.status = 'PASS'
                continue
            if _RE_END_FAIL.search(stripped):
                result.status = 'FAIL'
                result.errors.append(stripped)
                continue

            # ---- Transition header: "No.1 of 1 Transition -- TargetState: S3" ----
            m = _RE_TRANS_HEADER.match(stripped)
            if m:
                current_transition = PwrTestTransitionResult(
                    transition_number=int(m.group(1)),
                    total_transitions=int(m.group(2)),
                    target_state=m.group(3),
                )
                result.transitions.append(current_transition)
                result.total_cycles = int(m.group(2))
                continue

            # ---- Transition complete marker ----
            if _RE_TRANS_COMPLETE.match(stripped) and current_transition:
                current_transition.completed = True
                result.completed_cycles += 1
                current_transition = None
                continue

            # ---- Per-transition fields ----
            if current_transition is None:
                continue

            m = _RE_EFFECTIVE_STATE.match(stripped)
            if m:
                current_transition.effective_state = m.group(1)
                continue

            m = _RE_SLEEP_TIME.match(stripped)
            if m:
                current_transition.sleep_time_ms = int(m.group(1))
                continue

            m = _RE_BIOS_INIT.match(stripped)
            if m:
                current_transition.bios_init_time_ms = int(m.group(1))
                continue

            m = _RE_DRIVER_WAKE.match(stripped)
            if m:
                current_transition.driver_wake_time_ms = int(m.group(1))
                continue

            m = _RE_TRANS_START.match(stripped)
            if m:
                current_transition.start_time = m.group(1).strip()
                continue

            m = _RE_TRANS_END.match(stripped)
            if m:
                current_transition.end_time = m.group(1).strip()
                continue

        # If status was never explicitly set, it stays UNKNOWN
        logger.debug(
            f"_parse_log_text: status={result.status}, "
            f"transitions={len(result.transitions)}, "
            f"completed={result.completed_cycles}"
        )

    def _parse_xml_tree(
        self,
        root: ET.Element,
        result: 'PwrTestTestResult',
    ) -> None:
        """
        Parse an XML ElementTree root into *result* (mutates it).

        The XML schema is not publicly documented; this method uses a
        best-effort approach — an unknown structure yields status ``"UNKNOWN"``.
        """
        # Try to find a <Result> or <Verdict> element
        for tag in ('Result', 'Verdict', 'Status'):
            el = root.find(f'.//{tag}')
            if el is not None and el.text:
                text = el.text.strip().upper()
                if 'PASS' in text:
                    result.status = 'PASS'
                elif 'FAIL' in text:
                    result.status = 'FAIL'
                break

        # Count <Transition> elements
        transitions_xml = root.findall('.//Transition')
        result.total_cycles = len(transitions_xml)
        for t in transitions_xml:
            pd = PwrTestTransitionResult(
                total_transitions=len(transitions_xml),
                target_state=t.get('TargetState', ''),
                effective_state=t.get('EffectiveState', ''),
                completed=(t.get('Status', '').upper() == 'COMPLETE'),
            )
            for child in t:
                tag = child.tag
                text = (child.text or '').strip()
                if tag == 'SleepTimeMs' and text.isdigit():
                    pd.sleep_time_ms = int(text)
                elif tag == 'BiosInitTimeMs' and text.isdigit():
                    pd.bios_init_time_ms = int(text)
                elif tag == 'DriverWakeTimeMs' and text.isdigit():
                    pd.driver_wake_time_ms = int(text)
            if pd.completed:
                result.completed_cycles += 1
            result.transitions.append(pd)

        # Collect <Error> text nodes
        for err in root.findall('.//Error'):
            if err.text:
                result.errors.append(err.text.strip())
