"""
Unit tests for lib.testtool.sleepstudy.exceptions
"""

import pytest

from lib.testtool.sleepstudy.exceptions import (
    SleepStudyError,
    SleepStudyConfigError,
    SleepStudyTimeoutError,
    SleepStudyProcessError,
    SleepStudyLogParseError,
    SleepStudyTestFailedError,
)


class TestExceptionHierarchy:
    """All custom exceptions must be sub-classes of SleepStudyError."""

    @pytest.mark.parametrize("exc_cls", [
        SleepStudyConfigError,
        SleepStudyTimeoutError,
        SleepStudyProcessError,
        SleepStudyLogParseError,
        SleepStudyTestFailedError,
    ])
    def test_inherits_from_base(self, exc_cls):
        assert issubclass(exc_cls, SleepStudyError)

    def test_base_inherits_exception(self):
        assert issubclass(SleepStudyError, Exception)


class TestExceptionRaise:
    """Each exception can be raised and caught."""

    @pytest.mark.parametrize("exc_cls, msg", [
        (SleepStudyError,          "base error"),
        (SleepStudyConfigError,    "bad config"),
        (SleepStudyTimeoutError,   "timed out"),
        (SleepStudyProcessError,   "process died"),
        (SleepStudyLogParseError,  "no data found"),
        (SleepStudyTestFailedError, "sw drips too low"),
    ])
    def test_raise_and_catch_by_base(self, exc_cls, msg):
        with pytest.raises(SleepStudyError, match=msg):
            raise exc_cls(msg)

    def test_catch_specific_type(self):
        with pytest.raises(SleepStudyConfigError):
            raise SleepStudyConfigError("invalid timeout: -1")

    def test_message_preserved(self):
        msg = "LocalSprData not found in sleepstudy-report.html"
        exc = SleepStudyLogParseError(msg)
        assert str(exc) == msg
