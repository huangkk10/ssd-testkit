"""
WAC View Results Reader

Reads the "View Results" page in Windows Assessment Console via pywinauto UIA.

After a BPFS assessment completes WAC switches to the View Results page.
This module:
  - Detects when the page has appeared (by polling for the "View Results" header)
  - Reads "Total errors" / "Total warnings" from the left-side Run information grid
  - Reads the "Results" path from the right-side System information panel
  - Returns all data as a WACRunResult dataclass

Note on auto_id:
  WAC uses WPF / UIA.  The exact automation IDs for the View Results DataGrid
  items depend on the build and cannot be known without running on a real machine.
  This module uses a robust name-matching strategy (search by visible text) plus a
  debug_enumerate_view_results() helper that logs every descendant so that
  auto_ids can be confirmed and the fallback paths hardened over time.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

from lib.logger import get_module_logger
from .exceptions import ADKResultError, ADKTimeoutError

logger = get_module_logger(__name__)

# Text that appears in the WAC breadcrumb / page header when the View Results
# page is active.  Checked case-insensitively.
_VIEW_RESULTS_HEADER = "View Results"


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------

@dataclass
class WACRunResult:
    """Parsed result from the WAC View Results page.

    Attributes:
        errors:            Total errors count from the Run information grid.
        warnings:          Total warnings count from the Run information grid.
        analysis_complete: Whether "Analysis complete" is True in the grid.
        result_path:       The filesystem path shown under System information
                           → Results (where WAC stored the assessment output).
        machine_name:      Machine name shown in the System information panel.
        run_time:          Timestamp string from the result list item header
                           (e.g. "3/23/2026 2:22:36 PM").
    """
    errors: int = 0
    warnings: int = 0
    analysis_complete: bool = False
    result_path: str = ""
    machine_name: str = ""
    run_time: str = ""


# ---------------------------------------------------------------------------
# Helpers — internal text extraction
# ---------------------------------------------------------------------------

def _int_from_text(text: str) -> int:
    """Extract the first integer found in *text*, return 0 on failure."""
    import re
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else 0


def _bool_from_text(text: str) -> bool:
    """Return True if *text* (case-insensitive) is 'true'."""
    return (text or "").strip().lower() == "true"


def _safe_name(ctrl) -> str:
    """Return the element name string, '' on any error."""
    try:
        return ctrl.element_info.name or ""
    except Exception:
        return ""


def _safe_value(ctrl) -> str:
    """Try get_value(), fall back to window_text(), '' on error."""
    for method in ("get_value", "window_text"):
        try:
            val = getattr(ctrl, method)()
            if val is not None:
                return str(val)
        except Exception:
            pass
    return ""


# ---------------------------------------------------------------------------
# Debug helper
# ---------------------------------------------------------------------------

def debug_enumerate_view_results(window) -> None:
    """Log every descendant of the WAC window for auto_id discovery.

    Call this once from test_03 while View Results is visible, then examine
    app.log to find the exact automation IDs for Total errors / Results path.

    Args:
        window: pywinauto WindowSpecification for the WAC main window.
    """
    logger.debug("[ViewResults DEBUG] Starting full descendants enumeration")
    try:
        all_ctrls = window.descendants()
        for idx, ctrl in enumerate(all_ctrls):
            try:
                info = ctrl.element_info
                name = info.name or ""
                aid = info.automation_id or ""
                ct = info.control_type or ""
                val = _safe_value(ctrl)
                logger.debug(
                    "[ViewResults DEBUG] [%d] ct=%-20s  aid=%-45s  name=%r  value=%r",
                    idx, ct, aid, name, val,
                )
            except Exception as exc:
                logger.debug("[ViewResults DEBUG] [%d] inspect error: %s", idx, exc)
    except Exception as exc:
        logger.debug("[ViewResults DEBUG] descendants() error: %s", exc)
    logger.debug("[ViewResults DEBUG] Enumeration complete")


# ---------------------------------------------------------------------------
# Page detection
# ---------------------------------------------------------------------------

def _is_view_results_visible(window) -> bool:
    """Return True if the View Results page header is currently visible."""
    try:
        # Strategy 1: find a Text control whose name == "View Results"
        texts = window.descendants(control_type="Text")
        for ctrl in texts:
            if _safe_name(ctrl).strip() == _VIEW_RESULTS_HEADER:
                return True
    except Exception:
        pass
    # Strategy 2: check window title / breadcrumb via window_text
    try:
        wt = window.window_text() or ""
        if _VIEW_RESULTS_HEADER in wt:
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Core reader
# ---------------------------------------------------------------------------

def read_view_results(window) -> WACRunResult:
    """Read the current state of the WAC View Results page.

    Assumes the View Results page is already visible.  Call
    wait_for_view_results() if you need to wait for it to appear.

    Reads:
    - Left-side Run information grid  → errors, warnings, analysis_complete
    - Right-side System information   → result_path, machine_name, run_time

    Args:
        window: pywinauto WindowSpecification for the WAC main window.

    Returns:
        WACRunResult populated with parsed values (defaults to 0 / "" if a
        field cannot be found — check app.log for DEBUG details).
    """
    result = WACRunResult()

    # --- Step 1: click the first result list item so the detail panel shows ---
    _click_first_result_item(window)
    time.sleep(0.5)   # allow panel to refresh

    # --- Step 2: read Run information DataGrid (left panel) ---
    _read_run_information(window, result)

    # --- Step 3: read System information panel (right panel) ---
    _read_system_information(window, result)

    logger.info(
        "[ViewResults] errors=%d  warnings=%d  analysis_complete=%s  "
        "machine=%r  result_path=%r",
        result.errors, result.warnings, result.analysis_complete,
        result.machine_name, result.result_path,
    )
    return result


def _click_first_result_item(window) -> None:
    """Click the first result/run item in the left-side list to populate the panel."""
    try:
        # The result list uses ListItem or custom DataGrid rows.
        # Try ListItem first (most common in WPF WAC builds).
        items = window.descendants(control_type="ListItem")
        if items:
            items[0].click_input()
            logger.debug("[ViewResults] Clicked first ListItem: %r", _safe_name(items[0]))
            return
        # Fallback: DataItem
        items = window.descendants(control_type="DataItem")
        if items:
            items[0].click_input()
            logger.debug("[ViewResults] Clicked first DataItem: %r", _safe_name(items[0]))
    except Exception as exc:
        logger.debug("[ViewResults] _click_first_result_item error (non-fatal): %s", exc)


def _read_run_information(window, result: WACRunResult) -> None:
    """Populate result.errors / warnings / analysis_complete from the DataGrid."""
    try:
        all_ctrls = window.descendants()
    except Exception as exc:
        logger.debug("[ViewResults] descendants() error: %s", exc)
        return

    # Build a flat list of (name, value) pairs from DataItem / Text controls.
    # We look for a label whose name contains the target string, then take the
    # next sibling's value as the number.

    prev_name = ""
    for ctrl in all_ctrls:
        try:
            ct = (ctrl.element_info.control_type or "").lower()
            name = _safe_name(ctrl).strip()
            val = _safe_value(ctrl).strip()

            if ct == "dataitem":
                # DataItem rows often embed the label and value as children
                try:
                    children = ctrl.children()
                    texts = [_safe_value(c) or _safe_name(c) for c in children]
                    row_text = " ".join(texts)
                except Exception:
                    row_text = name + " " + val

                row_lower = row_text.lower()
                if "total errors" in row_lower:
                    result.errors = _int_from_text(row_text)
                    logger.debug("[ViewResults] total errors row: %r → %d", row_text, result.errors)
                elif "total warnings" in row_lower:
                    result.warnings = _int_from_text(row_text)
                    logger.debug("[ViewResults] total warnings row: %r → %d", row_text, result.warnings)
                elif "analysis complete" in row_lower:
                    result.analysis_complete = _bool_from_text(row_text.split()[-1] if row_text else "")
                    logger.debug("[ViewResults] analysis_complete row: %r → %s", row_text, result.analysis_complete)

            elif ct == "text":
                # Consecutive Text pairs: label then value
                name_lower = name.lower()
                if "total errors" in name_lower:
                    result.errors = _int_from_text(val or name)
                elif "total warnings" in name_lower:
                    result.warnings = _int_from_text(val or name)
                elif prev_name.lower() in ("total errors",):
                    result.errors = _int_from_text(name or val)
                elif prev_name.lower() in ("total warnings",):
                    result.warnings = _int_from_text(name or val)
                prev_name = name

        except Exception as exc:
            logger.debug("[ViewResults] row parse error: %s", exc)


def _read_system_information(window, result: WACRunResult) -> None:
    """Populate result.result_path / machine_name / run_time from the right panel."""
    try:
        all_ctrls = window.descendants()
    except Exception as exc:
        logger.debug("[ViewResults] _read_system_information descendants error: %s", exc)
        return

    prev_name = ""
    for ctrl in all_ctrls:
        try:
            ct = (ctrl.element_info.control_type or "").lower()
            name = _safe_name(ctrl).strip()
            val  = _safe_value(ctrl).strip()
            aid  = (ctrl.element_info.automation_id or "").lower()

            # Auto_id based match (highest confidence if IDs are known)
            if "result" in aid and ("path" in aid or "value" in aid or aid.endswith("result")):
                if val and not result.result_path:
                    result.result_path = val
                    logger.debug("[ViewResults] result_path via auto_id=%r: %r", aid, val)
                    continue

            if ct in ("text", "hyperlink", "edit"):
                name_lower = name.lower()
                prev_lower = prev_name.lower()

                # "Results" label followed by its value
                if name_lower == "results" and not val:
                    prev_name = name
                    continue
                if prev_lower == "results" and (val or name):
                    candidate = val or name
                    if candidate and "\\" in candidate:  # looks like a path
                        result.result_path = candidate
                        logger.debug("[ViewResults] result_path from label pair: %r", candidate)

                # "Name" → machine name (first occurrence before "Results")
                if name_lower == "name" and not val:
                    prev_name = name
                    continue
                if prev_lower == "name" and (val or name) and not result.machine_name:
                    result.machine_name = val or name
                    logger.debug("[ViewResults] machine_name: %r", result.machine_name)

                prev_name = name

            # Hyperlink: WAC renders the Results path as a clickable link
            if ct == "hyperlink":
                candidate = val or name
                if candidate and "\\" in candidate and not result.result_path:
                    result.result_path = candidate
                    logger.debug("[ViewResults] result_path from Hyperlink: %r", candidate)

        except Exception as exc:
            logger.debug("[ViewResults] system info parse error: %s", exc)


# ---------------------------------------------------------------------------
# Public waiting function
# ---------------------------------------------------------------------------

def wait_for_view_results(
    window,
    timeout: int = 7200,
    poll: int = 10,
    debug_enumerate: bool = False,
) -> WACRunResult:
    """Wait for the WAC View Results page then read and return results.

    Polls the WAC window every *poll* seconds until the View Results header
    is detected, then calls read_view_results().

    Args:
        window:          pywinauto WindowSpecification for the WAC main window.
        timeout:         Maximum seconds to wait (default 7200 = 2 hours).
        poll:            Polling interval in seconds (default 10).
        debug_enumerate: If True, run debug_enumerate_view_results() once when
                         the page first appears (logs all descendants for
                         auto_id discovery).  Set to True during initial
                         bring-up on a new machine/build.

    Returns:
        WACRunResult

    Raises:
        ADKTimeoutError: View Results page did not appear within *timeout* seconds.
    """
    deadline = time.monotonic() + timeout
    elapsed_log_interval = 60  # log "still waiting" every N seconds
    last_log = time.monotonic()

    logger.info("[ViewResults] Waiting for View Results page (timeout=%ds)", timeout)

    while time.monotonic() < deadline:
        if _is_view_results_visible(window):
            logger.info("[ViewResults] View Results page detected")
            if debug_enumerate:
                debug_enumerate_view_results(window)
            return read_view_results(window)

        now = time.monotonic()
        if now - last_log >= elapsed_log_interval:
            remaining = int(deadline - now)
            logger.info(
                "[ViewResults] Still waiting for View Results page "
                "(remaining=%ds)", remaining
            )
            last_log = now

        time.sleep(poll)

    raise ADKTimeoutError(
        f"View Results page did not appear within {timeout}s"
    )
