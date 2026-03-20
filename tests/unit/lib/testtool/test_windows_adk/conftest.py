"""
Shared pytest fixtures for windows_adk unit tests.
"""

import os
import tempfile
import textwrap

import pytest


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def temp_log_path(temp_dir):
    return temp_dir


# ---------------------------------------------------------------------------
# Sample AxeLog fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def axelog_passed(temp_dir):
    """AxeLog.txt that contains exit code=0 (success)."""
    path = os.path.join(temp_dir, "AxeLog.txt")
    content = (
        "OnAssessmentEnd (assessment #0) error=0x00000000, exit code=0 (0x00000000)\n"
    )
    with open(path, "w", encoding="utf-16-le") as fp:
        fp.write(content)
    return path


@pytest.fixture
def axelog_failed(temp_dir):
    """AxeLog.txt that does NOT contain exit code=0."""
    path = os.path.join(temp_dir, "AxeLog.txt")
    with open(path, "w", encoding="utf-16-le") as fp:
        fp.write("Some other content\n")
    return path


# ---------------------------------------------------------------------------
# Sample Assessment XML fixture
# Two iterations, each with one TestCase entry per metric key.
# ---------------------------------------------------------------------------

def _make_xml_with_iterations(iterations: list) -> str:
    """Build a minimal Assessment XML string with given iteration data.

    Each item in *iterations* is a list of (key, metric_values) tuples where
    metric_values is a list of Value strings.
    """
    iter_blocks = []
    for i, test_cases in enumerate(iterations):
        tc_blocks = []
        for key, values in test_cases:
            mv_blocks = "".join(
                f'<MetricValue><Value>{v}</Value></MetricValue>' for v in values
            )
            tc_blocks.append(
                f'<TestCase><Key>{key}</Key>'
                f'<MetricValues>{mv_blocks}</MetricValues></TestCase>'
            )
        iter_blocks.append(
            f'<Iteration><TestCases>{"".join(tc_blocks)}</TestCases></Iteration>'
        )
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <AxeJobResults>
          <AssessmentResults>
            <AssessmentResult>
              <Iterations>
                {"".join(iter_blocks)}
              </Iterations>
            </AssessmentResult>
          </AssessmentResults>
        </AxeJobResults>
    """)


@pytest.fixture
def bpfs_xml_results():
    """Parsed dict for a BPFS assessment with 2 iterations.

    Suspend=6s, Resume=10s (should PASS with default thresholds 8s, 12s).
    MetricValue[1] is the primary value, so we need index 1 to be the target.
    We use [dummy, value] for each metric.
    """
    import xmltodict
    xml = _make_xml_with_iterations([
        [
            ("FastStartup-Suspend-Overall-Time", ["0", "6"]),
            ("FastStartup-Resume-Overall-Time",  ["0", "10"]),
        ],
        [
            ("FastStartup-Suspend-Overall-Time", ["0", "6"]),
            ("FastStartup-Resume-Overall-Time",  ["0", "10"]),
        ],
    ])
    return xmltodict.parse(xml)


@pytest.fixture
def bpfs_xml_results_fail_suspend():
    """Parsed dict: Suspend=9s (fails threshold of 8s)."""
    import xmltodict
    xml = _make_xml_with_iterations([
        [
            ("FastStartup-Suspend-Overall-Time", ["0", "9"]),
            ("FastStartup-Resume-Overall-Time",  ["0", "10"]),
        ],
    ])
    return xmltodict.parse(xml)


@pytest.fixture
def standby_xml_results():
    """Parsed dict: Standby suspend=3s, resume=2s (should PASS)."""
    import xmltodict
    xml = _make_xml_with_iterations([
        [
            ("Standby-Suspend-Overall-Time", ["0", "3"]),
            ("Standby-Resume-Overall-Time",  ["0", "2"]),
        ],
        [
            ("Standby-Suspend-Overall-Time", ["0", "3"]),
            ("Standby-Resume-Overall-Time",  ["0", "2"]),
        ],
    ])
    return xmltodict.parse(xml)


@pytest.fixture
def hiberfile_xml_results():
    """Parsed dict for HiberFileRead check.

    MetricValue[0]=duration_ms, MetricValue[1]=dummy, MetricValue[2]=size_kb.
    2048 KB / 1024 MB = 2 MB  read in 2 ms → 1000 MB/s > 500 spec → PASS.
    """
    import xmltodict
    xml = _make_xml_with_iterations([
        [("FastStartup-Resume-ReadHiberFile", ["2", "0", "2048"])],
        [("FastStartup-Resume-ReadHiberFile", ["2", "0", "2048"])],
    ])
    return xmltodict.parse(xml)
