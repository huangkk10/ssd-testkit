"""
PHM (Powerhouse Mountain) HTML Log Parser

Parses the HTML report files produced by PHM after a test run.
PHM exports results as an HTML file; this module extracts the
key fields needed for pass/fail determination and error reporting.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

from .exceptions import PHMLogParseError
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class PHMTestResult:
    """
    Parsed result from a single PHM HTML report.

    Attributes:
        status:            Overall test verdict: ``"PASS"``, ``"FAIL"``, or ``"UNKNOWN"``.
        total_cycles:      Number of cycles that were configured.
        completed_cycles:  Number of cycles that actually completed.
        errors:            List of error messages found in the report.
        start_time:        Test start timestamp string (as printed in the HTML).
        end_time:          Test end timestamp string (as printed in the HTML).
        raw_html_path:     Absolute path to the source HTML file.
        test_name:         Test name/title extracted from the report.
        platform_info:     Platform / system info string if present.
    """
    status: str = 'UNKNOWN'
    total_cycles: int = 0
    completed_cycles: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    raw_html_path: str = ''
    test_name: str = ''
    platform_info: str = ''


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class PHMLogParser:
    """
    Parser for PHM HTML report files.

    PHM generates an HTML log after each test session.  This class reads that
    file and returns a :class:`PHMTestResult` with all relevant fields filled.

    .. note::
        The exact HTML structure depends on the installed PHM version.  The
        patterns used here target **PHM 4.22.x**.  If a future version changes
        the report layout, update ``_PATTERNS`` and the parsing methods.

    Example:
        >>> parser = PHMLogParser()
        >>> result = parser.parse_html_report('./testlog/PHMLog/report.html')
        >>> print(result.status)
        PASS
    """

    # ------------------------------------------------------------------
    # Regex patterns (case-insensitive) — to be validated against real HTML
    # once PHM is installed and a sample report is captured.
    # ------------------------------------------------------------------
    _PATTERNS = {
        # Overall verdict line: "Test Result: PASS" or "Overall Result: FAIL"
        'status':           re.compile(
            r'(?:test|overall)\s+result\s*[:\-]\s*(PASS|FAIL)',
            re.IGNORECASE
        ),
        # Cycle counts: "Cycles: 10 / 10" or "Completed Cycles: 8"
        'total_cycles':     re.compile(
            r'(?:total\s+)?cycles\s*[:\-]\s*(\d+)',
            re.IGNORECASE
        ),
        'completed_cycles': re.compile(
            r'completed\s+cycles\s*[:\-]\s*(\d+)',
            re.IGNORECASE
        ),
        # Timestamps: "Start Time: 2026-03-02 10:00:00"
        'start_time':       re.compile(
            r'start\s+(?:time|date)\s*[:\-]\s*([^\n<]+)',
            re.IGNORECASE
        ),
        'end_time':         re.compile(
            r'(?:end|stop|finish)\s+(?:time|date)\s*[:\-]\s*([^\n<]+)',
            re.IGNORECASE
        ),
        # Test name / title: first <h1> or <title> tag
        'test_name':        re.compile(
            r'<(?:h1|title)[^>]*>\s*([^<]+?)\s*</(?:h1|title)>',
            re.IGNORECASE
        ),
        # Error lines: any row containing "ERROR" or "FAIL" with a message
        'error_line':       re.compile(
            r'(?:error|failure)\s*[:\-]\s*([^\n<]{5,})',
            re.IGNORECASE
        ),
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_html_report(self, html_path: str) -> PHMTestResult:
        """
        Parse a single PHM HTML report file.

        Args:
            html_path: Path to the HTML report file.

        Returns:
            :class:`PHMTestResult` populated from the report contents.

        Raises:
            PHMLogParseError: If the file cannot be read or the expected
                              report structure is not found.

        Example:
            >>> result = PHMLogParser().parse_html_report('./report.html')
            >>> assert result.status in ('PASS', 'FAIL', 'UNKNOWN')
        """
        html_path = str(html_path)
        path = Path(html_path)

        if not path.exists():
            raise PHMLogParseError(f"HTML report not found: {html_path}")

        if path.stat().st_size == 0:
            raise PHMLogParseError(f"HTML report is empty: {html_path}")

        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except OSError as exc:
            raise PHMLogParseError(f"Cannot read HTML report: {html_path}") from exc

        if not content.strip():
            raise PHMLogParseError(f"HTML report has no content: {html_path}")

        result = PHMTestResult(raw_html_path=str(path.resolve()))

        # Strip HTML tags to get plain text for most regex matches
        plain = self._strip_html_tags(content)

        result.status           = self._parse_status(plain)
        result.total_cycles     = self._parse_total_cycles(plain)
        result.completed_cycles = self._parse_completed_cycles(plain)
        result.start_time       = self._parse_timestamp(plain, 'start_time')
        result.end_time         = self._parse_timestamp(plain, 'end_time')
        result.test_name        = self._parse_test_name(content)  # raw HTML for tags
        result.errors           = self._parse_errors(plain)
        result.platform_info    = self._parse_platform_info(plain)

        logger.info(
            f"Parsed PHM report: status={result.status} "
            f"completed={result.completed_cycles}/{result.total_cycles} "
            f"errors={len(result.errors)}"
        )
        return result

    def parse_html_reports_batch(self, log_dir: str) -> List[PHMTestResult]:
        """
        Parse all HTML reports found inside *log_dir*.

        Args:
            log_dir: Directory containing ``*.html`` PHM report files.

        Returns:
            List of :class:`PHMTestResult`, one per file, sorted by filename.

        Raises:
            PHMLogParseError: If *log_dir* does not exist.
        """
        log_path = Path(log_dir)
        if not log_path.exists():
            raise PHMLogParseError(f"Log directory not found: {log_dir}")

        html_files = sorted(log_path.glob('*.html'))
        if not html_files:
            logger.warning(f"No HTML reports found in: {log_dir}")
            return []

        results = []
        for html_file in html_files:
            try:
                results.append(self.parse_html_report(str(html_file)))
            except PHMLogParseError as exc:
                logger.error(f"Failed to parse {html_file.name}: {exc}")
        return results

    @staticmethod
    def summarize(results: List[PHMTestResult]) -> dict:
        """
        Generate a summary dictionary from a list of results.

        Args:
            results: List returned by :meth:`parse_html_reports_batch`.

        Returns:
            ``{'total': int, 'pass': int, 'fail': int, 'unknown': int,
               'error_summary': List[str]}``
        """
        pass_count    = sum(1 for r in results if r.status == 'PASS')
        fail_count    = sum(1 for r in results if r.status == 'FAIL')
        unknown_count = sum(1 for r in results if r.status == 'UNKNOWN')
        all_errors: List[str] = []
        for r in results:
            all_errors.extend(r.errors)

        return {
            'total':         len(results),
            'pass':          pass_count,
            'fail':          fail_count,
            'unknown':       unknown_count,
            'error_summary': list(dict.fromkeys(all_errors)),  # de-dup, preserve order
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_html_tags(html: str) -> str:
        """Remove HTML tags and decode common entities."""
        text = re.sub(r'<[^>]+>', ' ', html)
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;',  '&')
        text = text.replace('&lt;',   '<')
        text = text.replace('&gt;',   '>')
        text = text.replace('&quot;', '"')
        # Collapse whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _parse_status(self, plain: str) -> str:
        """Extract PASS/FAIL verdict from plain text."""
        m = self._PATTERNS['status'].search(plain)
        if m:
            return m.group(1).upper()
        # Secondary heuristic: presence of error keyword without explicit verdict
        if re.search(r'\bFAIL\b', plain, re.IGNORECASE):
            return 'FAIL'
        if re.search(r'\bPASS\b', plain, re.IGNORECASE):
            return 'PASS'
        return 'UNKNOWN'

    def _parse_total_cycles(self, plain: str) -> int:
        m = self._PATTERNS['total_cycles'].search(plain)
        return int(m.group(1)) if m else 0

    def _parse_completed_cycles(self, plain: str) -> int:
        m = self._PATTERNS['completed_cycles'].search(plain)
        if m:
            return int(m.group(1))
        # Fallback: use total_cycles as completed if no separate field
        return self._parse_total_cycles(plain)

    def _parse_timestamp(self, plain: str, key: str) -> Optional[str]:
        m = self._PATTERNS[key].search(plain)
        return m.group(1).strip() if m else None

    def _parse_test_name(self, html: str) -> str:
        m = self._PATTERNS['test_name'].search(html)
        return m.group(1).strip() if m else ''

    def _parse_errors(self, plain: str) -> List[str]:
        errors = []
        for m in self._PATTERNS['error_line'].finditer(plain):
            msg = m.group(1).strip()
            if msg and msg not in errors:
                errors.append(msg)
        return errors

    @staticmethod
    def _parse_platform_info(plain: str) -> str:
        """Extract platform/system info if present (best-effort)."""
        m = re.search(
            r'(?:platform|system|model)\s*[:\-]\s*([^\n]{5,})',
            plain,
            re.IGNORECASE,
        )
        return m.group(1).strip() if m else ''
