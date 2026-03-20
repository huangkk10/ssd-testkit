"""
Windows ADK Result Parser

Pure data-processing module: reads AxeLog.txt and Assessment XML files,
computes per-iteration averages, and checks values against SPEC thresholds.

No pywinauto / GUI dependencies — all functions can be unit-tested offline.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

import xmltodict

from lib.logger import get_module_logger
from .config import DEFAULT_THRESHOLDS
from .exceptions import ADKResultError

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# AxeLog helpers
# ---------------------------------------------------------------------------

def parse_axelog(axelog_path: str) -> Tuple[bool, str]:
    """Read AxeLog.txt and determine whether the assessment succeeded.

    Returns:
        (True, "Result Passed") if ``exit code=0`` is found.
        (False, "Result Failed") if the file exists but exit code is absent.
        (False, <error message>) if the file cannot be opened.
    """
    try:
        with open(axelog_path, "r", encoding="utf-16-le") as fp:
            for line in fp:
                if "exit code=0" in line:
                    logger.info("Assessment finished with exit code=0")
                    return True, "Result Passed"
        return False, "Result Failed"
    except OSError as exc:
        msg = f"Cannot read AxeLog: {exc}"
        logger.error(msg)
        return False, msg


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def open_xml(filename: str, encoding: str = "utf8") -> dict:
    """Parse an Assessment XML file and return as a dict."""
    try:
        with open(filename, encoding=encoding) as fd:
            return xmltodict.parse(fd.read())
    except Exception as exc:
        logger.error(f"Error opening/parsing XML file: {exc}")
        return {}


def _iteration_list(results: dict) -> list:
    """Safely return the list of Iteration dicts from a parsed XML result.

    xmltodict returns a dict (not list) when there is only one <Iteration>,
    so we always normalise to a list.
    """
    try:
        data = (
            results["AxeJobResults"]["AssessmentResults"]["AssessmentResult"]
            ["Iterations"]["Iteration"]
        )
        return data if isinstance(data, list) else [data]
    except (KeyError, TypeError):
        return []


def get_result_average(results: dict, key: str) -> float:
    """Compute the average MetricValue[1] across all iterations for *key*.

    MetricValue index 1 is the primary metric value used by the original ADK.py.
    """
    total = 0.0
    count = 0
    for iteration in _iteration_list(results):
        if "TestCases" not in iteration:
            continue
        test_cases = iteration["TestCases"].get("TestCase", [])
        if isinstance(test_cases, dict):
            test_cases = [test_cases]
        for tc in test_cases:
            if tc.get("Key") != key:
                continue
            raw = tc["MetricValues"]["MetricValue"][1]["Value"]
            total += float(raw)
            count += 1
    if count == 0:
        raise ADKResultError(f"No iterations found for key: {key}")
    avg = round(total / count, 3)
    logger.info(f"{key} = {avg}")
    return avg


def get_result_hiberfile_read(results: dict, key: str) -> Tuple[float, float]:
    """Return (avg_duration_ms, avg_hiberfile_size_kb) for HiberFileRead metrics.

    MetricValue indices used:
        [0] = duration (ms)
        [2] = OnOffHiberFileSizeKb
    """
    total_ms = 0.0
    total_kb = 0.0
    count = 0
    for iteration in _iteration_list(results):
        if "TestCases" not in iteration:
            continue
        test_cases = iteration["TestCases"].get("TestCase", [])
        if isinstance(test_cases, dict):
            test_cases = [test_cases]
        for tc in test_cases:
            if tc.get("Key") != key:
                continue
            metrics = tc["MetricValues"]["MetricValue"]
            total_ms += float(metrics[0]["Value"])
            total_kb += float(metrics[2]["Value"])
            count += 1
    if count == 0:
        raise ADKResultError(f"No iterations found for key: {key}")
    avg_ms = round(total_ms / count)
    avg_kb = round(total_kb / count)
    logger.info(f"{key} = {avg_ms} ms, HiberFileSizeKb = {avg_kb}")
    return avg_ms, avg_kb


def get_result_bios_post_time(results: dict, key: str) -> float:
    """Return average BIOS POST time (seconds) for BIOSPOSTTime metrics.

    Uses MetricValue index [1].
    """
    return get_result_average(results, key)


# ---------------------------------------------------------------------------
# SPEC check helpers
# ---------------------------------------------------------------------------

def check_result_bpfs(results: dict, thresholds: Optional[Dict] = None) -> Tuple[bool, str]:
    """Check Boot Performance Fast Startup suspend + resume overall times."""
    t = thresholds or DEFAULT_THRESHOLDS
    for key in ("FastStartup-Suspend-Overall-Time", "FastStartup-Resume-Overall-Time"):
        avg = get_result_average(results, key)
        spec = t[key]
        if avg >= spec:
            msg = f"Failed: {key} = {avg}s (spec < {spec}s)"
            logger.error(msg)
            return False, msg
        logger.info(f"Passed: {key} = {avg}s (spec < {spec}s)")
    return True, "Passed"


def check_result_standby(results: dict, thresholds: Optional[Dict] = None) -> Tuple[bool, str]:
    """Check Standby Performance suspend + resume overall times."""
    t = thresholds or DEFAULT_THRESHOLDS
    for key in ("Standby-Suspend-Overall-Time", "Standby-Resume-Overall-Time"):
        avg = get_result_average(results, key)
        spec = t[key]
        if avg >= spec:
            msg = f"Failed: {key} = {avg}s (spec < {spec}s)"
            logger.error(msg)
            return False, msg
        logger.info(f"Passed: {key} = {avg}s (spec < {spec}s)")
    return True, "Passed"


def check_result_hiberfile_read(results: dict, thresholds: Optional[Dict] = None) -> Tuple[bool, str]:
    """Check FastStartup HiberFile read throughput (MB/s must be > spec)."""
    t = thresholds or DEFAULT_THRESHOLDS
    key = "FastStartup-Resume-ReadHiberFile"
    spec = t[key]
    avg_ms, avg_kb = get_result_hiberfile_read(results, "FastStartup-Resume-ReadHiberFile")
    # throughput = (size_kb / 1024 MB) / (duration_ms / 1000 s)
    throughput = round((avg_kb / 1024) / (avg_ms / 1000))
    if throughput <= spec:
        msg = f"Failed: {key} = {throughput} MB/s (spec > {spec} MB/s)"
        logger.error(msg)
        return False, msg
    logger.info(f"Passed: {key} = {throughput} MB/s (spec > {spec} MB/s)")
    return True, "Passed"


def check_result_bios_post_time(results: dict, thresholds: Optional[Dict] = None) -> Tuple[bool, str]:
    """Check FastStartup BIOS POST time (seconds must be < spec)."""
    t = thresholds or DEFAULT_THRESHOLDS
    key = "FastStartup-Resume-BIOS"
    spec = t[key]
    avg = get_result_bios_post_time(results, key)
    if avg >= spec:
        msg = f"Failed: {key} = {avg}s (spec < {spec}s)"
        logger.error(msg)
        return False, msg
    logger.info(f"Passed: {key} = {avg}s (spec < {spec}s)")
    return True, "Passed"


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def read_result_xml(result_dir_path: str, username: str, result_dir_name: str) -> dict:
    """Load the Assessment XML from the standard WAC result directory."""
    xml_path = os.path.join(
        result_dir_path, result_dir_name, f"{result_dir_name}.xml"
    )
    results = open_xml(xml_path, encoding="utf8")
    if not results:
        raise ADKResultError(f"Failed to parse result XML: {xml_path}")
    return results


def save_result(source_dir: str, dest_dir: str, result_dir_name: str) -> None:
    """Copy Assessment result directory from source to dest and write JSON."""
    source = os.path.join(source_dir, result_dir_name)
    dest = os.path.abspath(os.path.join(dest_dir, result_dir_name))
    logger.info(f"Saving result: {source} -> {dest}")
    shutil.copytree(source, dest)


def dump_result_json(results: dict, log_path: str, result_dir_name: str) -> None:
    """Write parsed XML dict as formatted JSON to the log directory."""
    json_path = os.path.abspath(os.path.join(log_path, f"{result_dir_name}.json"))
    with open(json_path, "w") as fp:
        json.dump(results, fp, indent=4)
    logger.info(f"Result JSON saved: {json_path}")
