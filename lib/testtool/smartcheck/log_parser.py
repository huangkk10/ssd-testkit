"""
SmartCheckLogParser — parse NVMe Log Page 0x2 tables from SmartCheck.log.

SmartCheck.bat appends one NVMe Log Page 0x2 Data table per polling cycle to
SmartCheck.log.  Each table looks like:

    ===== NVMe Log Page 0x2 Data =====
    +---...---+
    |     Offset  Curr Value       Prev Value       Init Value       Description     |
    +---...---+
    |     0:0     00               ...              ...              Critical Warning |
    |     7F:70   000000000000002F ...              ...              Power Cycles     |
    ...
    +---...---+

This module provides :class:`SmartCheckLogParser` which:

- Parses *any* SmartCheck.log file and extracts attribute Curr Values as integers.
- Compares two log files (before / after) and reports which attributes increased.

Typical usage in a test step::

    from lib.testtool.smartcheck import SmartCheckLogParser

    parser = SmartCheckLogParser([
        "Critical Warning",
        "Power Cycles",
        "Unsafe Shutdowns",
        "Media and Data Integrity Errors",
        "Number of Error Information Log Entries",
    ])
    ok, failures = parser.compare_no_increase(
        before_log=Path('./testlog/SmartCheckLog_before/SmartCheck.log'),
        after_log=Path('./testlog/SmartCheckLog_after/SmartCheck.log'),
    )
    if not ok:
        pytest.fail("\\n".join(failures))
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lib.logger import get_module_logger

logger = get_module_logger(__name__)

_NVME_TABLE_MARKER = "===== NVMe Log Page 0x2 Data ====="


def _parse_nvme_row(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (curr_hex_str, description) from one NVMe table data row.

    Returns (None, None) for header / separator / non-data lines.

    Row format (pipe-delimited, fixed-width)::

        |     0:0     00               0022             0020             Critical Warning  |

    The offset token is always ``<hex>:<hex>``.  Curr Value is the next hex
    token.  Description is reconstructed from the trailing non-hex tokens.
    """
    content = line.strip().strip('|').strip()
    if not content:
        return None, None
    # Skip header row and separator lines
    if (content.startswith('Offset')
            or content.startswith('-')
            or content.startswith('+')):
        return None, None

    tokens = content.split()
    if len(tokens) < 2:
        return None, None

    # tokens[0] = offset ("0:0", "7F:70", …)
    # tokens[1] = Curr Value (hex, may be empty-column → next hex token)
    curr_hex = tokens[1]
    if not re.match(r'^[0-9A-Fa-f]+$', curr_hex):
        return None, None

    # Description: trailing tokens that are NOT pure hex strings
    desc_tokens: List[str] = []
    for tok in reversed(tokens[2:]):
        if re.match(r'^[0-9A-Fa-f]+$', tok):
            break
        desc_tokens.insert(0, tok)

    if not desc_tokens:
        return None, None

    return curr_hex, ' '.join(desc_tokens)


class SmartCheckLogParser:
    """Parse NVMe Log Page 0x2 tables from SmartCheck.log and compare snapshots.

    Args:
        monitored_attributes: List of NVMe attribute description strings to
            track.  Only these attributes are extracted and compared.
            If *None*, all attributes found in the table are returned.

    Example::

        parser = SmartCheckLogParser([
            "Critical Warning",
            "Unsafe Shutdowns",
            "Media and Data Integrity Errors",
            "Number of Error Information Log Entries",
        ])

        before = parser.parse(Path('./testlog/SmartCheckLog_before/SmartCheck.log'))
        after  = parser.parse(Path('./testlog/SmartCheckLog_after/SmartCheck.log'))

        ok, failures = parser.compare_no_increase(before=before, after=after)
    """

    def __init__(self, monitored_attributes: Optional[List[str]] = None) -> None:
        self.monitored_attributes = monitored_attributes

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse(self, log_path: Path) -> Dict[str, int]:
        """Parse the *last* NVMe Log Page 0x2 table in *log_path*.

        Returns:
            ``{description: curr_value_as_int}`` dict for each row whose
            description is in :attr:`monitored_attributes` (or all rows when
            ``monitored_attributes`` is *None*).

        Raises:
            FileNotFoundError: if *log_path* does not exist.
            ValueError: if the NVMe table marker is not found in the file.
        """
        if not log_path.exists():
            raise FileNotFoundError(f"SmartCheck log not found: {log_path}")

        text = log_path.read_text(encoding='utf-8', errors='replace')

        last_idx = text.rfind(_NVME_TABLE_MARKER)
        if last_idx == -1:
            raise ValueError(
                f"NVMe Log Page 0x2 Data table not found in {log_path}"
            )

        section = text[last_idx:]
        result: Dict[str, int] = {}
        for line in section.splitlines():
            if not line.startswith('|'):
                continue
            curr_hex, description = _parse_nvme_row(line)
            if curr_hex is None or description is None:
                continue
            want = self.monitored_attributes
            if want is None or description in want:
                result[description] = int(curr_hex, 16)

        logger.debug(f"Parsed {len(result)} attribute(s) from {log_path.name}")
        return result

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    def compare_no_increase(
        self,
        before_log: Optional[Path] = None,
        after_log: Optional[Path] = None,
        *,
        before: Optional[Dict[str, int]] = None,
        after: Optional[Dict[str, int]] = None,
    ) -> Tuple[bool, List[str]]:
        """Assert that monitored Curr Values did not increase.

        You may supply either log *Path* objects (will be parsed internally)
        or pre-parsed dicts (useful when you already called :meth:`parse`).

        Args:
            before_log: Path to the before-SmartCheck.log.
            after_log:  Path to the after-SmartCheck.log.
            before:     Pre-parsed before dict (overrides *before_log*).
            after:      Pre-parsed after dict (overrides *after_log*).

        Returns:
            ``(True, [])`` when all attributes pass.
            ``(False, [failure_message, ...])`` when any attribute increased or
            could not be parsed.

        Raises:
            ValueError: if neither log paths nor pre-parsed dicts are provided.
        """
        if before is None:
            if before_log is None:
                raise ValueError("Provide either 'before_log' or 'before'")
            before = self.parse(before_log)
        if after is None:
            if after_log is None:
                raise ValueError("Provide either 'after_log' or 'after'")
            after = self.parse(after_log)

        attrs = self.monitored_attributes or sorted(set(before) | set(after))
        failures: List[str] = []

        for attr in attrs:
            b = before.get(attr)
            a = after.get(attr)
            if b is None or a is None:
                msg = f"[{attr}] could not be parsed (before={b}, after={a})"
                failures.append(msg)
                logger.warning(msg)
            elif a > b:
                msg = f"[{attr}] increased: {b:#018x} → {a:#018x} (+{a - b})"
                failures.append(msg)
                logger.error(msg)
            else:
                logger.info(f"[SmartCheckLogParser] OK  {attr}: {b:#018x} → {a:#018x}")

        return (len(failures) == 0), failures

    def compare_must_be_zero(
        self,
        log: Optional[Path] = None,
        *,
        values: Optional[Dict[str, int]] = None,
        attributes: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """Assert that each monitored attribute equals zero.

        Args:
            log:        Path to SmartCheck.log to check.
            values:     Pre-parsed dict (overrides *log*).
            attributes: Subset of attributes to check (defaults to
                        :attr:`monitored_attributes` or all parsed attrs).

        Returns:
            ``(True, [])`` when all zero; ``(False, [failure_message, ...])`` otherwise.
        """
        if values is None:
            if log is None:
                raise ValueError("Provide either 'log' or 'values'")
            values = self.parse(log)

        attrs = attributes or self.monitored_attributes or sorted(values)
        failures: List[str] = []
        for attr in attrs:
            v = values.get(attr)
            if v is None:
                msg = f"[{attr}] could not be parsed"
                failures.append(msg)
                logger.warning(msg)
            elif v != 0:
                msg = f"[{attr}] is not zero: {v:#018x} ({v})"
                failures.append(msg)
                logger.error(msg)
            else:
                logger.info(f"[SmartCheckLogParser] OK  {attr} == 0")

        return (len(failures) == 0), failures
