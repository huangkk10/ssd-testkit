"""
SmiCli Controller

Threading-based controller for executing SmiCli2.exe and collecting DUT information.

This module provides:
- SmiCliDiskType  — disk type hex constants
- SmiCliProtocolType — protocol type hex constants
- SmiCliController — main threading controller
"""

import os
import pathlib
import subprocess
import threading
import time
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.logger import get_module_logger
from .config import SmiCliConfig
from .exceptions import (
    SmiCliConfigError,
    SmiCliTimeoutError,
    SmiCliProcessError,
    SmiCliTestFailedError,
)

logger = get_module_logger(__name__)

# Executable filename
_EXE_NAME = "SmiCli2.exe"

# Path under SSD_TESTKIT_ROOT (post-chocolatey layout)
_REL_PATH_TESTKIT = os.path.join("bin", "installers", "SmiCli", _EXE_NAME)

# Legacy relative path (pre-chocolatey layout, kept for backward compatibility)
_LEGACY_REL_PATH = os.path.join(".\\bin\\SmiCli", _EXE_NAME)


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

class SmiCliDiskType:
    """SmiCli disk type constants (matches SmiCli2.exe --info output)."""
    DISK_TYPE_HDD         = 0x2
    DISK_TYPE_SATA        = 0x120
    DISK_TYPE_NVME        = 0x140
    DISK_TYPE_UFD         = 0x180
    DISK_TYPE_SM2320      = 0x181
    DISK_TYPE_UFD_NOT_SMI = 0x18F
    DISK_TYPE_SATA_PWR_1  = 0x200
    DISK_TYPE_SATA_PWR_2  = 0x201
    DISK_TYPE_PCIE_PWR_1  = 0x202
    DISK_TYPE_PCIE_PWR_2  = 0x203


class SmiCliProtocolType:
    """SmiCli protocol type constants (matches SmiCli2.exe --info output)."""
    PROTOCOL_TYPE_ATA_OVER_ATA           = 0x10
    PROTOCOL_TYPE_ATA_OVER_USB           = 0x11
    PROTOCOL_TYPE_ATA_OVER_CSMI          = 0x12
    PROTOCOL_TYPE_NVME_OVER_STORNVME     = 0x20
    PROTOCOL_TYPE_NVME_OVER_SCSIMINIPORT = 0x21
    PROTOCOL_TYPE_NVME_OVER_IRST         = 0x22
    PROTOCOL_TYPE_SCSI                   = 0x40


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class SmiCliController(threading.Thread):
    """
    Controller for executing SmiCli2.exe and collecting DUT information.

    Inherits from ``threading.Thread`` so it can run asynchronously or be
    called synchronously via ``start()`` + ``join()``.

    SmiCli2.exe path resolution order (first non-empty value wins):
      1. ``smicli_path`` constructor argument
      2. ``SMICLI_PATH`` environment variable
      3. ``<SSD_TESTKIT_ROOT>\\bin\\installers\\SmiCli\\SmiCli2.exe``
      4. Legacy default: ``<work_dir>\\bin\\SmiCli\\SmiCli2.exe``

    Attributes:
        status (Optional[bool]): ``None`` while running, ``True`` on success,
                                 ``False`` on failure.
        error_message (str): Human-readable error description (empty on success).

    Example:
        >>> controller = SmiCliController(output_file="./testlog/DUT_Info.ini")
        >>> controller.start()
        >>> controller.join(timeout=90)
        >>> if controller.status:
        ...     print("DUT info collected successfully")
        ... else:
        ...     print(f"Failed: {controller.error_message}")
    """

    def __init__(
        self,
        output_file: str,
        smicli_path: str = '',
        work_dir: str = '',
        **kwargs,
    ) -> None:
        """
        Initialize SmiCliController.

        Args:
            output_file: Absolute (or relative-to-work_dir) path for the
                         output ``.ini`` file produced by SmiCli2.exe.
            smicli_path: Explicit path to SmiCli2.exe. Empty string triggers
                         the automatic resolution order.
            work_dir:    Working directory for the subprocess. Empty string
                         defaults to ``os.getcwd()`` at run time.
            **kwargs:    Additional configuration overrides (``timeout_seconds``,
                         ``post_run_wait_seconds``). Unknown keys raise
                         ``SmiCliConfigError``.

        Raises:
            SmiCliConfigError: If ``output_file`` is empty or kwargs contain
                               unknown / wrongly-typed parameters.
        """
        super().__init__()

        if not output_file:
            raise SmiCliConfigError("output_file must not be empty")

        base = SmiCliConfig.get_default_config()
        overrides = {'smicli_path': smicli_path, 'output_file': output_file, 'work_dir': work_dir}
        overrides.update(kwargs)
        SmiCliConfig.validate_config({k: v for k, v in overrides.items() if k in SmiCliConfig.VALID_PARAMS})

        self._config = SmiCliConfig.merge_config(base, overrides)

        self._stop_event = threading.Event()
        self._status: Optional[bool] = None
        self.error_message: str = ''

    def set_config(self, **kwargs) -> None:
        """
        Update configuration before the thread is started.

        Args:
            **kwargs: Configuration keys from ``SmiCliConfig.DEFAULT_CONFIG``.

        Raises:
            SmiCliConfigError: If unknown or wrongly-typed parameters are given.
        """
        SmiCliConfig.validate_config(kwargs)
        self._config.update(kwargs)

    @property
    def status(self) -> Optional[bool]:
        """``None`` while running, ``True`` on success, ``False`` on failure."""
        return self._status

    @property
    def error_count(self) -> int:
        """Returns 0 on success, 1 on any failure (SmiCli is a single-shot tool)."""
        return 0 if self._status else 1

    def stop(self) -> None:
        """Signal the controller to stop (no-op for SmiCli; it is single-shot)."""
        self._stop_event.set()

    def run(self) -> None:
        """Thread body: resolve exe path → run SmiCli2.exe → validate output."""
        try:
            work_dir = self._config['work_dir'] or os.getcwd()
            output_file = self._config['output_file']
            timeout = int(self._config['timeout_seconds'])
            wait = float(self._config['post_run_wait_seconds'])

            # Absolutize output_file
            if not os.path.isabs(output_file):
                output_file = os.path.join(work_dir, output_file)

            exe = self._resolve_exe_path(work_dir)

            if not os.path.exists(exe):
                raise SmiCliProcessError(f"{_EXE_NAME} not found: {exe}")

            # Ensure output directory exists
            pathlib.Path(os.path.dirname(output_file)).mkdir(parents=True, exist_ok=True)

            command = [exe, "--info", f"--outfile={output_file}"]
            logger.info(f"Executing: {' '.join(command)}")
            logger.info(f"Working directory: {work_dir}")

            try:
                result = subprocess.run(
                    command,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                raise SmiCliTimeoutError(
                    f"{_EXE_NAME} execution timeout ({timeout} seconds)"
                )
            except FileNotFoundError:
                raise SmiCliProcessError(f"{_EXE_NAME} not found: {exe}")

            logger.info(f"Return code: {result.returncode}")
            if result.stderr:
                logger.error(f"stderr: {result.stderr}")

            if result.returncode != 0:
                detail = result.stderr.strip() or "Unknown error"
                raise SmiCliProcessError(
                    f"{_EXE_NAME} failed (exit {result.returncode}): {detail}"
                )

            time.sleep(wait)

            if not os.path.exists(output_file):
                raise SmiCliTestFailedError(
                    f"{_EXE_NAME} completed but output file not found: {output_file}"
                )

            content = _read_file_with_fallback_encoding(output_file)
            if not content:
                raise SmiCliTestFailedError(
                    f"{_EXE_NAME} completed but output file is empty: {output_file}"
                )

            if "[info]" not in content and "[disk_" not in content:
                raise SmiCliTestFailedError(
                    f"Output file format is abnormal (missing [info]/[disk_*]): {output_file}"
                )

            logger.info(f"{_EXE_NAME} executed successfully → {output_file}")
            self._status = True

        except (SmiCliProcessError, SmiCliTimeoutError, SmiCliTestFailedError) as exc:
            logger.error(str(exc))
            self.error_message = str(exc)
            self._status = False
        except Exception as exc:
            msg = f"Unexpected error running {_EXE_NAME}: {exc}"
            logger.error(msg)
            self.error_message = msg
            self._status = False

    # ------------------------------------------------------------------
    # Exe path resolution
    # ------------------------------------------------------------------

    def _resolve_exe_path(self, work_dir: str) -> str:
        """Return absolute path to SmiCli2.exe following the resolution order."""
        smicli_path = self._config.get('smicli_path', '')

        if smicli_path:
            if not os.path.isabs(smicli_path):
                smicli_path = os.path.join(work_dir, smicli_path)
            return smicli_path

        env_path = os.environ.get("SMICLI_PATH")
        if env_path:
            return env_path

        testkit_root = os.environ.get("SSD_TESTKIT_ROOT")
        if testkit_root:
            return os.path.join(testkit_root, _REL_PATH_TESTKIT)

        return os.path.join(work_dir, _LEGACY_REL_PATH)

    # ------------------------------------------------------------------
    # Disk type / protocol type helpers (static)
    # ------------------------------------------------------------------

    _DISK_TYPE_NAMES: Dict[int, str] = {
        SmiCliDiskType.DISK_TYPE_HDD:         "HDD",
        SmiCliDiskType.DISK_TYPE_SATA:        "SATA",
        SmiCliDiskType.DISK_TYPE_NVME:        "NVMe",
        SmiCliDiskType.DISK_TYPE_UFD:         "USB Flash Drive",
        SmiCliDiskType.DISK_TYPE_SM2320:      "SM2320",
        SmiCliDiskType.DISK_TYPE_UFD_NOT_SMI: "USB Flash Drive (Non-SMI)",
        SmiCliDiskType.DISK_TYPE_SATA_PWR_1:  "SATA Power Board V1",
        SmiCliDiskType.DISK_TYPE_SATA_PWR_2:  "SATA Power Board V2",
        SmiCliDiskType.DISK_TYPE_PCIE_PWR_1:  "PCIe Power Board V1",
        SmiCliDiskType.DISK_TYPE_PCIE_PWR_2:  "PCIe Power Board V2",
    }

    _PROTOCOL_TYPE_NAMES: Dict[int, str] = {
        SmiCliProtocolType.PROTOCOL_TYPE_ATA_OVER_ATA:           "ATA over ATA",
        SmiCliProtocolType.PROTOCOL_TYPE_ATA_OVER_USB:           "ATA over USB",
        SmiCliProtocolType.PROTOCOL_TYPE_ATA_OVER_CSMI:          "ATA over CSMI",
        SmiCliProtocolType.PROTOCOL_TYPE_NVME_OVER_STORNVME:     "NVMe over StorNVMe",
        SmiCliProtocolType.PROTOCOL_TYPE_NVME_OVER_SCSIMINIPORT: "NVMe over SCSI Miniport",
        SmiCliProtocolType.PROTOCOL_TYPE_NVME_OVER_IRST:         "NVMe over iRST",
        SmiCliProtocolType.PROTOCOL_TYPE_SCSI:                   "SCSI",
    }

    _USB_TYPES = frozenset({
        SmiCliDiskType.DISK_TYPE_UFD,
        SmiCliDiskType.DISK_TYPE_SM2320,
        SmiCliDiskType.DISK_TYPE_UFD_NOT_SMI,
    })

    _POWER_BOARD_TYPES = frozenset({
        SmiCliDiskType.DISK_TYPE_SATA_PWR_1,
        SmiCliDiskType.DISK_TYPE_SATA_PWR_2,
        SmiCliDiskType.DISK_TYPE_PCIE_PWR_1,
        SmiCliDiskType.DISK_TYPE_PCIE_PWR_2,
    })

    @staticmethod
    def get_disk_type_name(disk_type_value: int) -> str:
        """Return human-readable name for a disk_type value."""
        return SmiCliController._DISK_TYPE_NAMES.get(
            disk_type_value, f"Unknown (0x{disk_type_value:X})"
        )

    @staticmethod
    def get_protocol_type_name(protocol_type_value: int) -> str:
        """Return human-readable name for a protocol_type value."""
        return SmiCliController._PROTOCOL_TYPE_NAMES.get(
            protocol_type_value, f"Unknown (0x{protocol_type_value:X})"
        )

    @staticmethod
    def is_nvme_disk(disk_type_value: int) -> bool:
        """Return True if the disk type represents an NVMe device."""
        return disk_type_value == SmiCliDiskType.DISK_TYPE_NVME

    @staticmethod
    def is_usb_disk(disk_type_value: int) -> bool:
        """Return True if the disk type represents a USB Flash Drive."""
        return disk_type_value in SmiCliController._USB_TYPES

    @staticmethod
    def is_power_board_disk(disk_type_value: int) -> bool:
        """Return True if the disk type represents a Power Board device."""
        return disk_type_value in SmiCliController._POWER_BOARD_TYPES


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_file_with_fallback_encoding(file_path: str) -> str:
    """Read a text file trying UTF-8, then CP950 (Traditional Chinese Windows), then latin-1."""
    for enc in ("utf-8", "cp950", "latin-1"):
        try:
            with open(file_path, "r", encoding=enc) as fh:
                return fh.read()
        except (UnicodeDecodeError, LookupError):
            continue
    return ""
