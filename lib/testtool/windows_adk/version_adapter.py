"""
Windows ADK Version Adapter

Encapsulates all per-OS-build differences: directory paths and any
UI-behaviour variations so the rest of the library stays version-agnostic.
"""

import getpass
from typing import Optional

from .config import SUPPORTED_BUILDS, TEST_RESULT_DIRS
from .exceptions import ADKError


class VersionAdapter:
    """Resolves build-specific paths and behaviour for a given Windows build number.

    Args:
        build_number: Integer Windows build number (e.g. 26100 for 24H2).
        username:     Windows username used to construct user-profile paths.
                      Defaults to the current user via getpass.getuser().
    """

    def __init__(self, build_number: int, username: Optional[str] = None):
        self.build_number = build_number
        self.username = username or getpass.getuser()
        if not self.is_supported():
            raise ADKError(
                f"Unsupported Windows build: {build_number}. "
                f"Supported builds: {sorted(SUPPORTED_BUILDS.keys())}"
            )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_supported(self) -> bool:
        """Return True if the build number is in the supported list."""
        return self.build_number in SUPPORTED_BUILDS

    def os_name(self) -> str:
        """Human-readable OS name for this build (e.g. 'Windows 11 24H2')."""
        return SUPPORTED_BUILDS[self.build_number]

    def get_test_dir(self) -> str:
        """Return the directory WAC writes in-flight results to during assessment.

        This is the directory polled while waiting for the assessment to finish.
        The trailing space in the template is stripped here.
        """
        template = TEST_RESULT_DIRS[self.build_number].strip()
        return template.format(user=self.username)

    def get_result_dir(self) -> str:
        """Return the final Assessment Results directory for this user.

        WAC moves results here when the assessment is complete.
        """
        return rf"C:\Users\{self.username}\Documents\Assessment Results\ ".strip()

    def get_job_dir(self) -> str:
        """Return the WAC Jobs directory for this user."""
        return rf"C:\Users\{self.username}\Documents\Windows Assessment Console\Jobs"
