"""
Unit tests for lib.testtool.reboot.exceptions.

Verifies the exception inheritance hierarchy and that each class
can be raised and caught as expected.
"""
import pytest

from lib.testtool.reboot.exceptions import (
    OsRebootError,
    OsRebootConfigError,
    OsRebootTimeoutError,
    OsRebootProcessError,
    OsRebootStateError,
    OsRebootTestFailedError,
)


# ------------------------------------------------------------------ #
# Inheritance checks                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("exc_class", [
    OsRebootConfigError,
    OsRebootTimeoutError,
    OsRebootProcessError,
    OsRebootStateError,
    OsRebootTestFailedError,
])
def test_all_subclass_of_base(exc_class):
    """Every specific exception must be a subclass of OsRebootError."""
    assert issubclass(exc_class, OsRebootError)


def test_base_is_exception():
    assert issubclass(OsRebootError, Exception)


# ------------------------------------------------------------------ #
# Raise-and-catch                                                      #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("exc_class, message", [
    (OsRebootError,           "base error"),
    (OsRebootConfigError,     "bad config"),
    (OsRebootTimeoutError,    "timed out"),
    (OsRebootProcessError,    "process died"),
    (OsRebootStateError,      "state file corrupt"),
    (OsRebootTestFailedError, "cycle incomplete"),
])
def test_raise_and_catch_specific(exc_class, message):
    with pytest.raises(exc_class, match=message):
        raise exc_class(message)


@pytest.mark.parametrize("exc_class", [
    OsRebootConfigError,
    OsRebootTimeoutError,
    OsRebootProcessError,
    OsRebootStateError,
    OsRebootTestFailedError,
])
def test_catch_as_base(exc_class):
    """Specific exceptions must be catchable as OsRebootError."""
    with pytest.raises(OsRebootError):
        raise exc_class("caught as base")


def test_exception_message_preserved():
    msg = "custom message 123"
    exc = OsRebootConfigError(msg)
    assert str(exc) == msg
