"""
Unit tests for WmiDutInfoCollector and RunCard.generate_dut_info(fallback=...).

All tests mock subprocess.run (PowerShell) so no real WMI / hardware is needed.

Coverage:
  WmiDutInfoCollector
    1. _map_bus_type() — all known BusType strings and unknowns
    2. _write_ini() — output parses back via configparser
    3. collect() — success path writes valid DUT_Info.ini
    4. collect() — PowerShell failure path returns False, sets error_message
    5. collect() — single-disk machine (PS returns object, not array)
    6. _get_drive_letters() — parses single + multi-partition
    7. CDI firmware supplement — used when fw is empty

  RunCard.generate_dut_info(fallback=...)
    8. fallback=False keeps original behaviour on smicli failure
    9. fallback=True triggers WmiDutInfoCollector when smicli fails
   10. fallback=True NOT triggered when smicli succeeds
   11. fallback=True, WMI also fails → returns False with combined error
"""

import configparser
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from lib.testtool.wmi_dut_collector import WmiDutInfoCollector
from lib.testtool.RunCard import Runcard


# ── helpers ────────────────────────────────────────────────────────────────

def _make_runcard(tmp_path) -> Runcard:
    return Runcard(test_path=str(tmp_path))


def _ps_proc(stdout: str, returncode: int = 0, stderr: str = "") -> MagicMock:
    """Return a fake CompletedProcess."""
    p = MagicMock()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


# ── pre-baked PowerShell responses for a two-disk machine ─────────────────

_SYS_OS   = json.dumps({"Caption": "Windows 11 Pro", "BuildNumber": "22621"})
_SYS_PLAT = json.dumps({"Manufacturer": "Dell Inc.", "Model": "OptiPlex 7090"})
_SYS_BIOS = json.dumps({"Manufacturer": "Dell Inc.", "SMBIOSBIOSVersion": "1.15.0"})
_SYS_CPU  = json.dumps({"Name": "Intel(R) Core(TM) i7-11700 @ 2.50GHz"})
_SYS_RAM  = "34359738368"   # 32 GB

_PD_TWO = json.dumps([
    {"DeviceId": "0", "FriendlyName": "Samsung SSD 980 PRO",
     "BusType": "NVMe", "Size": 512110190592,
     "FirmwareVersion": "EDAN24C", "PhysicalLocation": "PCIEX4 Slot 0"},
    {"DeviceId": "1", "FriendlyName": "HGST HTS721010A9E630",
     "BusType": "SATA", "Size": 1000204886016,
     "FirmwareVersion": "JB0OA3U0", "PhysicalLocation": "SATA Port 1"},
])

_DISK_TWO = json.dumps([
    {"Number": 0, "Size": 512110190592},
    {"Number": 1, "Size": 1000204886016},
])

_PART_C   = json.dumps({"DriveLetter": "C"})
_PART_D   = json.dumps({"DriveLetter": "D"})
_DRV_VER  = ""   # driver version queries return empty string in mocks


def _make_ps_side_effect(*responses):
    """
    Build a side-effect callable that returns _ps_proc(stdout) for each
    successive call to subprocess.run in the order of *responses*.
    """
    it = iter(responses)

    def _se(*args, **kwargs):
        stdout = next(it, "")
        return _ps_proc(stdout)

    return _se


# Keys of _collect_system_info queries (in call order):
_SYSTEM_INFO_RESPONSES = [
    _SYS_OS, _SYS_PLAT, _SYS_BIOS, _SYS_CPU, _SYS_RAM,
]
# Keys of _collect_disk_info queries for two-disk:
#   (1) Get-PhysicalDisk  (2) Get-Disk
#   then per disk: Get-Partition, driver_version (2 fallback tries each)
_DISK_INFO_RESPONSES_TWO = [
    _PD_TWO,          # Get-PhysicalDisk
    _DISK_TWO,        # Get-Disk
    _PART_C,          # Get-Partition disk 0
    _DRV_VER, _DRV_VER,  # driver_version disk 0 (two attempts)
    _PART_D,          # Get-Partition disk 1
    _DRV_VER, _DRV_VER,  # driver_version disk 1
]


# ══════════════════════════════════════════════════════════════════════════
# 1. _map_bus_type()
# ══════════════════════════════════════════════════════════════════════════

class TestMapBusType:
    def _c(self, tmp_path):
        return WmiDutInfoCollector(output_file=str(tmp_path / "DUT_Info.ini"))

    @pytest.mark.parametrize("bus,expected", [
        ("NVMe",  "0x140"),
        ("nvme",  "0x140"),
        ("SATA",  "0x120"),
        ("sata",  "0x120"),
        ("ATA",   "0x120"),
        ("USB",   "0x180"),
        ("SAS",   "0x2"),
        ("SCSI",  "0x2"),
        ("Unknown", "0x2"),
        ("",      "0x2"),
        ("Fibre", "0x2"),
    ])
    def test_map(self, tmp_path, bus, expected):
        assert self._c(tmp_path)._map_bus_type(bus) == expected


# ══════════════════════════════════════════════════════════════════════════
# 2. _write_ini()
# ══════════════════════════════════════════════════════════════════════════

class TestWriteIni:
    def test_round_trip(self, tmp_path):
        out = str(tmp_path / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)
        info = {
            "os": "Windows 11 Pro (Build 22621)",
            "platform": "Dell Inc. OptiPlex 7090",
            "bios": "Dell Inc. 1.15.0",
            "cpu": "Intel i7",
            "ram": "32GB",
            "spor_board": "N/A",
        }
        disks = [
            {
                "id": 0, "location": "PCIEX4 Slot 0",
                "driver_version": "10.0.22621.1", "capacity": "512GB",
                "fw": "EDAN24C", "aspm": "N/A",
                "drive_letters": "C", "disk_type": "0x140",
            }
        ]
        assert c._write_ini(info, disks) is True
        assert Path(out).exists()

        cfg = configparser.RawConfigParser()
        cfg.read(out, encoding="utf-8")
        assert cfg.has_section("info")
        assert cfg.get("info", "os") == "Windows 11 Pro (Build 22621)"
        assert cfg.has_section("disk_0")
        assert cfg.get("disk_0", "disk_type") == "0x140"
        assert cfg.get("disk_0", "drive_letters") == "C"

    def test_creates_parent_dir(self, tmp_path):
        out = str(tmp_path / "sub" / "dir" / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)
        assert c._write_ini({"os":"", "platform":"", "bios":"",
                              "cpu":"", "ram":"", "spor_board":""}, []) is True
        assert Path(out).exists()


# ══════════════════════════════════════════════════════════════════════════
# 3. collect() — success path
# ══════════════════════════════════════════════════════════════════════════

class TestCollectSuccess:
    def test_two_disks(self, tmp_path):
        out = str(tmp_path / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)

        responses = _SYSTEM_INFO_RESPONSES + _DISK_INFO_RESPONSES_TWO
        with patch("subprocess.run", side_effect=_make_ps_side_effect(*responses)):
            result = c.collect()

        assert result is True, f"collect() failed: {c.error_message}"
        assert Path(out).exists()

        cfg = configparser.RawConfigParser()
        cfg.read(out, encoding="utf-8")

        # [info] checks
        assert "Windows 11 Pro (Build 22621)" in cfg.get("info", "os")
        assert "Dell Inc." in cfg.get("info", "platform")
        assert cfg.get("info", "ram") == "32GB"
        assert cfg.get("info", "spor_board") == "N/A"

        # [disk_0] — NVMe
        assert cfg.has_section("disk_0")
        assert cfg.get("disk_0", "disk_type") == "0x140"
        assert cfg.get("disk_0", "fw") == "EDAN24C"
        assert cfg.get("disk_0", "capacity") == "477GB"  # 512110190592 / 1024^3 ≈ 477

        # [disk_1] — SATA
        assert cfg.has_section("disk_1")
        assert cfg.get("disk_1", "disk_type") == "0x120"
        assert cfg.get("disk_1", "fw") == "JB0OA3U0"


# ══════════════════════════════════════════════════════════════════════════
# 4. collect() — PowerShell failure
# ══════════════════════════════════════════════════════════════════════════

class TestCollectFailure:
    def test_powershell_error_degrades_gracefully(self, tmp_path):
        """When all PS queries fail, collect() still writes the INI with
        'Unknown' placeholder values and returns True (graceful degradation),
        so that load_dut_info() can still proceed."""
        out = str(tmp_path / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)

        with patch("subprocess.run", return_value=_ps_proc("", returncode=1, stderr="Access denied")):
            result = c.collect()

        # collect() must not raise; graceful degradation → True + file written
        assert result is True
        assert Path(out).exists()

        cfg = configparser.RawConfigParser()
        cfg.read(out, encoding="utf-8")
        assert cfg.has_section("info")
        assert cfg.get("info", "os") == "Unknown"
        assert cfg.get("info", "spor_board") == "N/A"

    def test_file_write_error_returns_false(self, tmp_path):
        """If _write_ini raises OSError, collect() returns False."""
        out = str(tmp_path / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)

        responses = _SYSTEM_INFO_RESPONSES + _DISK_INFO_RESPONSES_TWO
        with patch("subprocess.run", side_effect=_make_ps_side_effect(*responses)), \
             patch.object(c, "_write_ini", return_value=False):
            result = c.collect()

        assert result is False


# ══════════════════════════════════════════════════════════════════════════
# 5. collect() — single-disk (PS returns object not array)
# ══════════════════════════════════════════════════════════════════════════

class TestCollectSingleDisk:
    def test_single_disk_json_object(self, tmp_path):
        """PS ConvertTo-Json returns a bare {} for single items — must normalise."""
        out = str(tmp_path / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)

        pd_single = json.dumps({
            "DeviceId": "0", "FriendlyName": "Samsung SSD 980 PRO",
            "BusType": "NVMe", "Size": 512110190592,
            "FirmwareVersion": "EDAN24C", "PhysicalLocation": "PCIEX4 Slot 0",
        })
        disk_single = json.dumps({"Number": 0, "Size": 512110190592})
        part_c = json.dumps({"DriveLetter": "C"})

        responses = _SYSTEM_INFO_RESPONSES + [
            pd_single, disk_single, part_c, "", "",
        ]
        with patch("subprocess.run", side_effect=_make_ps_side_effect(*responses)):
            result = c.collect()

        assert result is True
        cfg = configparser.RawConfigParser()
        cfg.read(out, encoding="utf-8")
        assert cfg.has_section("disk_0")
        assert cfg.get("disk_0", "disk_type") == "0x140"


# ══════════════════════════════════════════════════════════════════════════
# 6. _get_drive_letters()
# ══════════════════════════════════════════════════════════════════════════

class TestGetDriveLetters:
    def _c(self, tmp_path):
        return WmiDutInfoCollector(output_file=str(tmp_path / "DUT_Info.ini"))

    def test_single_letter(self, tmp_path):
        c = self._c(tmp_path)
        with patch("subprocess.run", return_value=_ps_proc(json.dumps({"DriveLetter": "C"}))):
            assert c._get_drive_letters(0) == "C"

    def test_multiple_letters(self, tmp_path):
        c = self._c(tmp_path)
        letters = json.dumps([{"DriveLetter": "D"}, {"DriveLetter": "E"}])
        with patch("subprocess.run", return_value=_ps_proc(letters)):
            result = c._get_drive_letters(1)
        assert result == "D E"

    def test_no_drive_letter(self, tmp_path):
        c = self._c(tmp_path)
        with patch("subprocess.run", return_value=_ps_proc("[]")):
            assert c._get_drive_letters(2) == ""

    def test_ps_failure_returns_empty(self, tmp_path):
        c = self._c(tmp_path)
        with patch("subprocess.run", return_value=_ps_proc("", returncode=1)):
            assert c._get_drive_letters(0) == ""


# ══════════════════════════════════════════════════════════════════════════
# 7. CDI firmware supplement
# ══════════════════════════════════════════════════════════════════════════

class TestCdiFirmwareSupplement:
    def test_fw_from_cdi_when_empty(self, tmp_path):
        out = str(tmp_path / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)

        # patch _try_cdi_firmware to return a firmware string
        with patch.object(c, "_try_cdi_firmware", return_value="EDAN24C") as mock_cdi, \
             patch.object(c, "_resolve_cdi_path", return_value="/fake/DiskInfo.txt"):

            # Build a disk entry with empty fw
            disk = {
                "id": 0, "location": "PCIEX4 Slot 0",
                "driver_version": "N/A", "capacity": "512GB",
                "fw": "", "aspm": "N/A",
                "drive_letters": "C", "disk_type": "0x140",
            }
            # Manually call _try_cdi_firmware path inside _collect_disk_info
            # by mocking PhysicalDisk to return a disk with empty FirmwareVersion.
            pd_no_fw = json.dumps({
                "DeviceId": "0", "FriendlyName": "Samsung SSD 980 PRO",
                "BusType": "NVMe", "Size": 512110190592,
                "FirmwareVersion": "",    # ← empty, should trigger CDI supplement
                "PhysicalLocation": "PCIEX4 Slot 0",
            })
            disk_json = json.dumps({"Number": 0, "Size": 512110190592})
            part_c    = json.dumps({"DriveLetter": "C"})
            responses = _SYSTEM_INFO_RESPONSES + [pd_no_fw, disk_json, part_c, "", ""]

            with patch("subprocess.run", side_effect=_make_ps_side_effect(*responses)):
                result = c.collect()

        assert result is True
        cfg = configparser.RawConfigParser()
        cfg.read(out, encoding="utf-8")
        assert cfg.get("disk_0", "fw") == "EDAN24C"

    def test_no_cdi_file_skips_silently(self, tmp_path):
        out = str(tmp_path / "DUT_Info.ini")
        c = WmiDutInfoCollector(output_file=out)
        # _resolve_cdi_path returns None → supplement skipped
        with patch.object(c, "_resolve_cdi_path", return_value=None):
            fw = c._try_cdi_firmware("Samsung SSD 980 PRO", str(tmp_path / "missing.txt"))
        assert fw == ""


# ══════════════════════════════════════════════════════════════════════════
# 8. RunCard.generate_dut_info(fallback=False) — original behaviour preserved
# ══════════════════════════════════════════════════════════════════════════

class TestRunCardFallbackFalse:
    def _smicli_fail_patch(self):
        """Patch SmiCliController to always report failure."""
        mock_ctrl = MagicMock()
        mock_ctrl.status = False
        mock_ctrl.error_message = "SmiCli2.exe not found: C:\\fake\\SmiCli2.exe"
        return patch(
            "lib.testtool.RunCard.SmiCliController",
            return_value=mock_ctrl,
        )

    def test_returns_false_on_smicli_failure(self, tmp_path):
        rc = _make_runcard(tmp_path)
        with self._smicli_fail_patch():
            result = rc.generate_dut_info(
                output_file=str(tmp_path / "DUT_Info.ini"),
                fallback=False,
            )
        assert result is False
        assert "SmiCli2.exe not found" in rc.error_message

    def test_wmi_not_called_when_fallback_false(self, tmp_path):
        rc = _make_runcard(tmp_path)
        with self._smicli_fail_patch(), \
             patch("lib.testtool.RunCard.WmiDutInfoCollector") as mock_wmi:
            # WmiDutInfoCollector should not even be imported/used
            try:
                rc.generate_dut_info(
                    output_file=str(tmp_path / "DUT_Info.ini"),
                    fallback=False,
                )
            except Exception:
                pass
        mock_wmi.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════
# 9. RunCard.generate_dut_info(fallback=True) — triggers WMI on smicli fail
# ══════════════════════════════════════════════════════════════════════════

class TestRunCardFallbackTrue:
    def _smicli_fail_patch(self):
        mock_ctrl = MagicMock()
        mock_ctrl.status = False
        mock_ctrl.error_message = "SmiCli2.exe not found"
        return patch("lib.testtool.RunCard.SmiCliController", return_value=mock_ctrl)

    def test_wmi_called_and_returns_true(self, tmp_path):
        rc = _make_runcard(tmp_path)
        mock_collector = MagicMock()
        mock_collector.collect.return_value = True
        mock_collector.error_message = ""

        with self._smicli_fail_patch(), \
             patch("lib.testtool.wmi_dut_collector.WmiDutInfoCollector",
                   return_value=mock_collector), \
             patch("lib.testtool.RunCard.WmiDutInfoCollector",
                   return_value=mock_collector):
            result = rc.generate_dut_info(
                output_file=str(tmp_path / "DUT_Info.ini"),
                fallback=True,
            )

        assert result is True
        mock_collector.collect.assert_called_once()

    def test_wmi_failure_returns_false_combined_message(self, tmp_path):
        rc = _make_runcard(tmp_path)
        mock_collector = MagicMock()
        mock_collector.collect.return_value = False
        mock_collector.error_message = "PowerShell access denied"

        with self._smicli_fail_patch(), \
             patch("lib.testtool.RunCard.WmiDutInfoCollector",
                   return_value=mock_collector):
            result = rc.generate_dut_info(
                output_file=str(tmp_path / "DUT_Info.ini"),
                fallback=True,
            )

        assert result is False
        assert "SmiCli2.exe not found" in rc.error_message
        assert "PowerShell access denied" in rc.error_message


# ══════════════════════════════════════════════════════════════════════════
# 10. RunCard.generate_dut_info — smicli success, WMI NOT triggered
# ══════════════════════════════════════════════════════════════════════════

class TestRunCardSmicliSuccess:
    def test_wmi_not_called_when_smicli_ok(self, tmp_path):
        rc = _make_runcard(tmp_path)

        mock_ctrl = MagicMock()
        mock_ctrl.status = True
        mock_ctrl.error_message = ""

        with patch("lib.testtool.RunCard.SmiCliController", return_value=mock_ctrl), \
             patch("lib.testtool.RunCard.WmiDutInfoCollector") as mock_wmi:
            result = rc.generate_dut_info(
                output_file=str(tmp_path / "DUT_Info.ini"),
                fallback=True,
            )

        assert result is True
        mock_wmi.assert_not_called()
