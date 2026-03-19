"""
Allure metadata helpers — bridge between log_phase / log_table and Allure labels.

These functions are safe to call even when allure-pytest is NOT installed;
the allure-specific parts are silently skipped.
"""
import logging

try:
    import allure as _allure
    _ALLURE_AVAILABLE = True
except ImportError:
    _ALLURE_AVAILABLE = False


def allure_phase(lgr: logging.Logger, phase_name: str) -> None:
    """Write a phase banner to the log AND mark the current Allure feature.

    Drop-in replacement for ``log_phase()`` when Allure integration is desired.

    Usage (identical to log_phase):
        from lib.allure_helper import allure_phase
        allure_phase(logger, "PRE-REBOOT")
    """
    from lib.logger import log_phase
    log_phase(lgr, phase_name)
    if _ALLURE_AVAILABLE:
        _allure.dynamic.feature(phase_name)

def write_allure_result_before_exit(
    request,
    status: str = "passed",
    message: str = "",
    description: str = "",
) -> None:
    """Write an Allure result JSON directly to allure-results/ BEFORE os._exit().

    allure-pytest stores test data in memory and only flushes to disk via
    ``pytest_runtest_makereport``.  When a test calls ``os._exit(0)`` (e.g.
    to trigger a system reboot) that hook never fires, so no result file is
    written.  Call this function *before* the exit to produce a proper record.

    Args:
        request:     pytest ``request`` fixture.
        status:      "passed" | "failed" | "broken" | "skipped"
        message:     Short status message shown in the Allure UI.
        description: Longer Markdown description shown in the report body.
    """
    try:
        import json
        import uuid as _uuid
        import time
        from pathlib import Path

        #  Locate allure-results directory 
        try:
            allure_dir = Path(request.config.getoption("--alluredir"))
        except Exception:
            allure_dir = Path("allure-results")

        if not allure_dir.is_absolute():
            # Make relative to project root so the file lands next to Phase-A
            # results, regardless of the cwd at call time.
            start = Path(__file__).resolve()
            for p in [start] + list(start.parents):
                if (p / "pytest.ini").exists():
                    allure_dir = p / allure_dir
                    break
            else:
                allure_dir = Path.cwd() / allure_dir

        allure_dir.mkdir(parents=True, exist_ok=True)

        #  Build suite labels from nodeid 
        # nodeid example:
        #   tests/integration/framework/test_reboot_allure_real.py
        #   ::TestRebootAllureReal::test_03_trigger_reboot
        node = request.node
        nodeid_parts = node.nodeid.split("::")
        file_path = Path(nodeid_parts[0]).with_suffix("")  # strip .py
        path_parts = file_path.parts   # ('tests','integration','framework','test_reboot_allure_real')

        parent_suite = ".".join(path_parts[:-1]) if len(path_parts) > 1 else ""
        suite        = path_parts[-1] if path_parts else ""
        sub_suite    = nodeid_parts[1] if len(nodeid_parts) > 2 else ""

        labels = []
        if parent_suite:
            labels.append({"name": "parentSuite", "value": parent_suite})
        if suite:
            labels.append({"name": "suite",       "value": suite})
        if sub_suite:
            labels.append({"name": "subSuite",    "value": sub_suite})

        # Propagate allure feature/epic/tag markers that were already set
        try:
            import allure as _a
            for marker in node.iter_markers():
                from conftest import _ALLURE_MARKER_MAP  # type: ignore[import]
                entry = _ALLURE_MARKER_MAP.get(marker.name)
                if entry:
                    ltype, lval = entry
                    labels.append({"name": ltype, "value": lval})
        except Exception:
            pass

        #  Compose the result dict 
        now_ms = int(time.time() * 1000)
        full_name = (
            ".".join(path_parts) + "." + sub_suite + "#" + node.name
            if sub_suite
            else ".".join(path_parts) + "#" + node.name
        )

        result: dict = {
            "uuid":     str(_uuid.uuid4()),
            "name":     node.name,
            "fullName": full_name,
            "status":   status,
            "stage":    "finished",
            "start":    now_ms - 50,
            "stop":     now_ms,
            "labels":   labels,
            "steps":    [],
            "attachments": [],
            "parameters":  [],
            "links":       [],
        }
        if message:
            result["statusDetails"] = {"message": message}
        if description:
            result["description"] = description

        result_path = allure_dir / f"{result['uuid']}-result.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[allure_helper] Flushed allure result for {node.name} -> {result_path.name}")

    except Exception as exc:
        print(f"[allure_helper] WARNING: write_allure_result_before_exit failed: {exc}")

