"""
WmiDutInfoCollector — Fallback DUT info collector using PowerShell / WMI.

When SmiCli2.exe is unavailable (non-SMI hardware, development machine, CI
environment), this module collects equivalent system and disk information
through Windows built-in PowerShell / WMI commands and writes the result as
a ``DUT_Info.ini`` file in the **same format** that SmiCli2.exe –-info
produces, so that ``RunCard.load_dut_info()`` can parse it without changes.

Output format::

    [info]
    os            = Windows 11 Pro (Build 22621)
    platform      = Dell Inc. OptiPlex 7090
    bios          = Dell Inc. 1.15.0
    cpu           = 11th Gen Intel(R) Core(TM) i7-11700 @ 2.50GHz
    ram           = 32GB
    spor_board    = N/A

    [disk_0]
    id            = 0
    location      = PCIEX4 Slot 0
    driver_version= 10.0.22621.1
    capacity      = 512GB
    fw            = EDAN24C
    aspm          = N/A
    drive_letters = C
    disk_type     = 0x140

Usage::

    from lib.testtool.wmi_dut_collector import WmiDutInfoCollector

    collector = WmiDutInfoCollector(output_file="./testlog/DUT_Info.ini")
    ok = collector.collect()
    if not ok:
        print(collector.error_message)
"""

import configparser
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.logger import get_module_logger

logger = get_module_logger(__name__)

# ---------------------------------------------------------------------------
# BusType → disk_type hex mapping (matches SmiCliDiskType constants)
# ---------------------------------------------------------------------------

_BUS_TYPE_MAP: Dict[str, str] = {
    "nvme": "0x140",   # DISK_TYPE_NVME
    "sata": "0x120",   # DISK_TYPE_SATA
    "ata":  "0x120",   # DISK_TYPE_SATA  (legacy PATA treated as SATA)
    "usb":  "0x180",   # DISK_TYPE_UFD
    "sas":  "0x2",     # DISK_TYPE_HDD
    "scsi": "0x2",     # DISK_TYPE_HDD
}
_BUS_TYPE_DEFAULT = "0x2"   # DISK_TYPE_HDD — safe unknown fallback


class WmiDutInfoCollector:
    """
    Fallback DUT info collector using PowerShell / WMI.

    Generates ``DUT_Info.ini`` in the same format as ``SmiCli2.exe --info``.

    Args:
        output_file:      Absolute (or cwd-relative) path for the output file.
        timeout_seconds:  Per-query PowerShell subprocess timeout (seconds).
        cdi_diskinfo_txt: Optional path to a CrystalDiskInfo ``DiskInfo.txt``
                          used to supplement missing firmware version strings.
    """

    def __init__(
        self,
        output_file: str,
        timeout_seconds: int = 60,
        cdi_diskinfo_txt: Optional[str] = None,
    ) -> None:
        if not output_file:
            raise ValueError("output_file must not be empty")
        self.output_file = os.path.abspath(output_file)
        self.timeout_seconds = int(timeout_seconds)
        self.cdi_diskinfo_txt = cdi_diskinfo_txt
        self.error_message: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> bool:
        """
        Execute PowerShell queries, build DUT_Info.ini, and write output_file.

        Returns:
            ``True`` on success, ``False`` on failure (``error_message`` is set).
        """
        try:
            info = self._collect_system_info()
            disks = self._collect_disk_info()
            return self._write_ini(info, disks)
        except Exception as exc:
            self.error_message = f"WmiDutInfoCollector.collect() unexpected error: {exc}"
            logger.error(self.error_message)
            return False

    # ------------------------------------------------------------------
    # System info ([info] section)
    # ------------------------------------------------------------------

    def _collect_system_info(self) -> Dict[str, str]:
        """Collect OS, platform, BIOS, CPU, and RAM via WMI / CIM."""
        info: Dict[str, str] = {}

        # OS caption + build number
        try:
            out = self._run_ps(
                "(Get-CimInstance Win32_OperatingSystem | "
                "Select-Object -Property Caption,BuildNumber | "
                "ConvertTo-Json -Compress)"
            )
            import json as _json
            d = _json.loads(out)
            caption = (d.get("Caption") or "").strip()
            build   = (d.get("BuildNumber") or "").strip()
            info["os"] = f"{caption} (Build {build})" if build else caption
        except Exception as exc:
            logger.warning(f"[WMI] os query failed: {exc}")
            info["os"] = "Unknown"

        # Platform (manufacturer + model)
        try:
            out = self._run_ps(
                "(Get-CimInstance Win32_ComputerSystem | "
                "Select-Object -Property Manufacturer,Model | "
                "ConvertTo-Json -Compress)"
            )
            import json as _json
            d = _json.loads(out)
            mfr   = (d.get("Manufacturer") or "").strip()
            model = (d.get("Model") or "").strip()
            info["platform"] = f"{mfr} {model}".strip()
        except Exception as exc:
            logger.warning(f"[WMI] platform query failed: {exc}")
            info["platform"] = "Unknown"

        # BIOS
        try:
            out = self._run_ps(
                "(Get-CimInstance Win32_BIOS | "
                "Select-Object -Property Manufacturer,SMBIOSBIOSVersion | "
                "ConvertTo-Json -Compress)"
            )
            import json as _json
            d = _json.loads(out)
            mfr = (d.get("Manufacturer") or "").strip()
            ver = (d.get("SMBIOSBIOSVersion") or "").strip()
            info["bios"] = f"{mfr} {ver}".strip()
        except Exception as exc:
            logger.warning(f"[WMI] bios query failed: {exc}")
            info["bios"] = "Unknown"

        # CPU (first processor)
        try:
            out = self._run_ps(
                "(Get-CimInstance Win32_Processor | "
                "Select-Object -First 1 -Property Name | "
                "ConvertTo-Json -Compress)"
            )
            import json as _json
            d = _json.loads(out)
            info["cpu"] = (d.get("Name") or "Unknown").strip()
        except Exception as exc:
            logger.warning(f"[WMI] cpu query failed: {exc}")
            info["cpu"] = "Unknown"

        # RAM (sum of physical memory sticks in GB)
        try:
            out = self._run_ps(
                "(Get-CimInstance Win32_PhysicalMemory | "
                "Measure-Object -Property Capacity -Sum).Sum"
            )
            total_bytes = int(out.strip())
            gb = round(total_bytes / (1024 ** 3))
            info["ram"] = f"{gb}GB"
        except Exception as exc:
            logger.warning(f"[WMI] ram query failed: {exc}")
            info["ram"] = "Unknown"

        info["spor_board"] = "N/A"

        logger.info(
            f"[WMI] system info: os={info['os']!r} platform={info['platform']!r} "
            f"bios={info['bios']!r} cpu={info['cpu']!r} ram={info['ram']!r}"
        )
        return info

    # ------------------------------------------------------------------
    # Disk info ([disk_N] sections)
    # ------------------------------------------------------------------

    def _collect_disk_info(self) -> List[Dict[str, Any]]:
        """
        Enumerate physical disks via Get-PhysicalDisk + Get-Disk + Get-Partition.

        Returns a list of dicts (one per disk), sorted by disk number.
        """
        import json as _json

        disks: List[Dict[str, Any]] = []

        # ── 1. Build a map: DiskNumber → PhysicalDisk properties ──────────
        try:
            pd_json = self._run_ps(
                "Get-PhysicalDisk | "
                "Select-Object DeviceId,FriendlyName,BusType,Size,"
                "FirmwareVersion,PhysicalLocation | "
                "ConvertTo-Json -Compress"
            )
            pd_raw = _json.loads(pd_json)
            # ConvertTo-Json returns a single object (not array) when there is
            # only one disk — normalise to list.
            if isinstance(pd_raw, dict):
                pd_raw = [pd_raw]
        except Exception as exc:
            logger.warning(f"[WMI] Get-PhysicalDisk failed: {exc}")
            pd_raw = []

        # Map DeviceId (string of disk number) → pd entry
        pd_map: Dict[str, Dict] = {}
        for pd in (pd_raw or []):
            dev_id = str(pd.get("DeviceId", "")).strip()
            if dev_id:
                pd_map[dev_id] = pd

        # ── 2. Enumerate disks via Get-Disk ────────────────────────────────
        try:
            disk_json = self._run_ps(
                "Get-Disk | Select-Object Number,Size | "
                "Sort-Object Number | ConvertTo-Json -Compress"
            )
            disk_raw = _json.loads(disk_json)
            if isinstance(disk_raw, dict):
                disk_raw = [disk_raw]
        except Exception as exc:
            logger.warning(f"[WMI] Get-Disk failed: {exc}")
            disk_raw = []

        # ── 3. For each disk, collect partitions and build the entry ───────
        for disk in (disk_raw or []):
            number = disk.get("Number")
            if number is None:
                continue
            number = int(number)
            num_str = str(number)

            pd_entry = pd_map.get(num_str, {})

            # Capacity
            raw_size = disk.get("Size") or pd_entry.get("Size") or 0
            try:
                capacity_gb = round(int(raw_size) / (1024 ** 3))
                capacity = f"{capacity_gb}GB"
            except (ValueError, TypeError):
                capacity = "Unknown"

            # BusType → disk_type hex
            bus_type = str(pd_entry.get("BusType") or "").strip()
            disk_type_hex = self._map_bus_type(bus_type)

            # Firmware version
            fw = str(pd_entry.get("FirmwareVersion") or "").strip()

            # Location
            location = str(pd_entry.get("PhysicalLocation") or "").strip()
            if not location:
                location = f"Disk {number}"

            # Drive letters for this disk
            drive_letters = self._get_drive_letters(number)

            # Driver version
            driver_version = self._get_driver_version(number)

            # Optional: supplement fw from CDI DiskInfo.txt
            model = str(pd_entry.get("FriendlyName") or "").strip()
            if not fw and model:
                cdi_path = self._resolve_cdi_path()
                if cdi_path:
                    fw = self._try_cdi_firmware(model, cdi_path)

            entry: Dict[str, Any] = {
                "id":             number,
                "location":       location or "N/A",
                "driver_version": driver_version or "N/A",
                "capacity":       capacity,
                "fw":             fw or "N/A",
                "aspm":           "N/A",
                "drive_letters":  drive_letters,
                "disk_type":      disk_type_hex,
            }
            disks.append(entry)
            logger.info(
                f"[WMI] disk_{number}: type={disk_type_hex} capacity={capacity} "
                f"fw={fw!r} letters={drive_letters!r}"
            )

        return disks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_ps(self, script: str) -> str:
        """
        Run a PowerShell command and return stdout as a string.

        Raises ``RuntimeError`` if the process exits with a non-zero code or
        if ``subprocess`` itself fails.
        """
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(
                f"PowerShell exited {result.returncode}: {stderr or '(no stderr)'}"
            )
        return (result.stdout or "").strip()

    def _map_bus_type(self, bus_type: str) -> str:
        """Map a ``Get-PhysicalDisk.BusType`` string to a SmiCliDiskType hex string."""
        return _BUS_TYPE_MAP.get(bus_type.lower().strip(), _BUS_TYPE_DEFAULT)

    def _get_drive_letters(self, disk_number: int) -> str:
        """
        Return a space-separated string of drive letters assigned to
        *disk_number* (e.g. ``"C D"``).  Returns ``""`` if none.
        """
        import json as _json
        try:
            out = self._run_ps(
                f"Get-Partition -DiskNumber {disk_number} "
                f"| Where-Object {{ $_.DriveLetter }} "
                f"| Select-Object DriveLetter "
                f"| ConvertTo-Json -Compress"
            )
            parts = _json.loads(out)
            if isinstance(parts, dict):
                parts = [parts]
            letters = [
                str(p.get("DriveLetter") or "").strip()
                for p in (parts or [])
                if p.get("DriveLetter")
            ]
            return " ".join(letters)
        except Exception as exc:
            logger.warning(f"[WMI] Get-Partition for disk {disk_number} failed: {exc}")
            return ""

    def _get_driver_version(self, disk_number: int) -> str:
        """
        Try to obtain the storage controller driver version for *disk_number*
        via ``Get-StorageReliabilityCounter`` or as a fallback via generic
        storage PnP device enumeration.

        Returns an empty string if not determinable.
        """
        try:
            # Query via Get-Disk → associated CIM_DiskDrive → PnP instance ID
            out = self._run_ps(
                f"$pnp = (Get-Disk -Number {disk_number} | "
                f"Get-PhysicalDisk | Get-StorageController | "
                f"Select-Object -ExpandProperty DeviceId -First 1 2>$null); "
                f"if ($pnp) {{ (Get-PnpDeviceProperty -InstanceId $pnp "
                f"-KeyName 'DEVPKEY_Device_DriverVersion' "
                f"-ErrorAction SilentlyContinue).Data }} else {{ '' }}"
            )
            return out.strip() or ""
        except Exception:
            pass

        # Fallback: query the OS driver version via Win32_PnPSignedDriver
        # for disk-type devices; take the first match.
        try:
            import json as _json
            out = self._run_ps(
                "(Get-CimInstance Win32_PnPSignedDriver "
                "| Where-Object { $_.DeviceClass -eq 'DiskDrive' } "
                "| Select-Object -First 1 DriverVersion "
                "| ConvertTo-Json -Compress)"
            )
            if out:
                d = _json.loads(out)
                return str(d.get("DriverVersion") or "").strip()
        except Exception:
            pass

        return ""

    def _resolve_cdi_path(self) -> Optional[str]:
        """
        Return the path to use for CDI supplementation.

        Priority:
          1. Explicit ``cdi_diskinfo_txt`` constructor argument.
          2. ``DiskInfo.txt`` in the same directory as ``output_file``.
        """
        if self.cdi_diskinfo_txt and os.path.isfile(self.cdi_diskinfo_txt):
            return self.cdi_diskinfo_txt
        candidate = os.path.join(os.path.dirname(self.output_file), "DiskInfo.txt")
        if os.path.isfile(candidate):
            return candidate
        return None

    def _try_cdi_firmware(self, disk_model: str, cdi_path: str) -> str:
        """
        Attempt to read the firmware version for *disk_model* from a
        CrystalDiskInfo ``DiskInfo.txt`` file via ``CDILogParser``.

        Returns the firmware string on success, ``""`` on any failure.
        """
        try:
            from lib.testtool.cdi.controller import CDILogParser
            data = CDILogParser().parse_file(cdi_path)
            for disk in data.get("disks", []):
                model_in_cdi = (disk.get("Model") or "").strip()
                if disk_model.lower() in model_in_cdi.lower() or \
                   model_in_cdi.lower() in disk_model.lower():
                    fw = (disk.get("Firmware") or disk.get("firmware") or "").strip()
                    if fw:
                        logger.info(
                            f"[WMI] CDI supplement: model={model_in_cdi!r} fw={fw!r}"
                        )
                        return fw
        except Exception as exc:
            logger.debug(f"[WMI] CDI firmware supplement skipped: {exc}")
        return ""

    # ------------------------------------------------------------------
    # INI writer
    # ------------------------------------------------------------------

    def _write_ini(self, info: Dict[str, str], disks: List[Dict[str, Any]]) -> bool:
        """
        Write collected data to ``output_file`` in DUT_Info.ini format.

        Returns ``True`` on success.
        """
        config = configparser.RawConfigParser()
        config.optionxform = str   # preserve case

        # [info] section
        config.add_section("info")
        for key in ("os", "platform", "bios", "cpu", "ram", "spor_board"):
            config.set("info", key, info.get(key, ""))

        # [disk_N] sections
        for disk in disks:
            section = f"disk_{disk['id']}"
            config.add_section(section)
            for key in ("id", "location", "driver_version",
                        "capacity", "fw", "aspm", "drive_letters", "disk_type"):
                config.set(section, key, str(disk.get(key, "")))

        # Ensure output directory exists
        Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.output_file, "w", encoding="utf-8") as fh:
                config.write(fh, space_around_delimiters=False)
            logger.info(f"[WMI] DUT_Info.ini written → {self.output_file}")
            return True
        except OSError as exc:
            self.error_message = f"Failed to write DUT_Info.ini: {exc}"
            logger.error(self.error_message)
            return False
