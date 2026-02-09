import os
import json
import configparser
import subprocess
import time
import pathlib
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple
import lib.logger as logger

try:
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


# SmiCli Disk Type Table
class SmiCliDiskType:
    """SmiCli Disk Type Definition"""
    DISK_TYPE_HDD = 0x2
    DISK_TYPE_SATA = 0x120
    DISK_TYPE_NVME = 0x140
    DISK_TYPE_UFD = 0x180
    DISK_TYPE_SM2320 = 0x181
    DISK_TYPE_UFD_NOT_SMI = 0x18F
    DISK_TYPE_SATA_PWR_1 = 0x200
    DISK_TYPE_SATA_PWR_2 = 0x201
    DISK_TYPE_PCIE_PWR_1 = 0x202
    DISK_TYPE_PCIE_PWR_2 = 0x203


# SmiCli Protocol Type Table
class SmiCliProtocolType:
    """SmiCli Protocol Type Definition"""
    PROTOCOL_TYPE_ATA_OVER_ATA = 0x10
    PROTOCOL_TYPE_ATA_OVER_USB = 0x11
    PROTOCOL_TYPE_ATA_OVER_CSMI = 0x12
    PROTOCOL_TYPE_NVME_OVER_STORNVME = 0x20
    PROTOCOL_TYPE_NVME_OVER_SCSIMINIPORT = 0x21
    PROTOCOL_TYPE_NVME_OVER_IRST = 0x22
    PROTOCOL_TYPE_SCSI = 0x40


class RuncardFormat(Enum):
    """Runcard Output Format Enumeration"""
    JSON = 1
    INI = 2


class DiskType(Enum):
    """Disk Type Enumeration"""
    PRIMARY = 0    # Primary Disk (C Drive)
    SECONDARY = 1  # Secondary Disk (Non-C Drive)


class TestResult(Enum):
    """Test Result Enumeration"""
    PASS = "PASS"
    FAIL = "FAIL"
    INTERRUPT = "Interrupt"
    ONGOING = "Ongoing"


class Runcard:
    """Runcard Class - Used for recording test status and results"""
    
    def __init__(self, test_path: str = "./testlog", test_case: str = "", script_version: str = "") -> None:
        """
        Initialize Runcard object
        
        Args:
            test_path (str): Test path, default is "./testlog"
            test_case (str): Test case name, e.g. "STC-1735"
            script_version (str): Script version, e.g. "1.0.0"
        """
        # Test path and time information
        self.path = os.path.abspath(test_path)
        self._start_time = datetime.now()
        self._end_time = datetime.now()
        
        # Test status information - Dynamic update
        self.test_result = TestResult.ONGOING.value
        self.test_cycle = -1
        self.error_message = "No Error"
        self.autoit_version = ""
        self.test_case = test_case
        self.script_version = script_version
        
        # System information - Load from DUT_Info.ini
        self.os = ""
        self.platform = ""
        self.bios = ""
        self.cpu = ""
        self.ram = ""
        self.spor_board = ""
        
        # Disk information - Load from DUT_Info.ini
        self.aspm = ""
        self.sample_capacity = ""
        self.controller_driver = ""
        self.sample_firmware = ""
        self.sample_slot = ""
        self.disk_number = ""
        self.sample_filesystem = ""
        
        # Initialize reload result tracking
        self._last_reload_result = None
    
    @property
    def start_time(self) -> str:
        """Get start time string"""
        return self._start_time.strftime("%Y/%m/%d %H:%M:%S")
    
    @start_time.setter
    def start_time(self, dt) -> None:
        """Set start time"""
        if isinstance(dt, datetime):
            self._start_time = dt
        elif isinstance(dt, str):
            try:
                self._start_time = datetime.strptime(dt, "%Y/%m/%d %H:%M:%S")
            except ValueError:
                logger.LogErr(f"Unable to parse start time format: {dt}")
    
    @property
    def end_time(self) -> str:
        """Get end time string"""
        return self._end_time.strftime("%Y/%m/%d %H:%M:%S")
    
    @end_time.setter
    def end_time(self, dt) -> None:
        """Set end time"""
        if isinstance(dt, datetime):
            self._end_time = dt
        elif isinstance(dt, str):
            try:
                self._end_time = datetime.strptime(dt, "%Y/%m/%d %H:%M:%S")
            except ValueError:
                logger.LogErr(f"Unable to parse end time format: {dt}")
    
    # sample_capacity is now a regular attribute (no filtering)
    
    @property
    def test_time(self) -> int:
        """Calculate test execution time (seconds)"""
        try:
            time_diff = self._end_time - self._start_time
            total_seconds = int(time_diff.total_seconds())
            
            # Check for negative numbers and log warning
            if total_seconds < 0:
                logger.LogErr(f"Detected negative test time: {total_seconds} seconds")
                logger.LogErr(f"Start time: {self.start_time}, End time: {self.end_time}")
                return 0
            
            return total_seconds
        except Exception as e:
            logger.LogErr(f"Failed to calculate test time: {str(e)}")
            return 0
    
    @property
    def test_hour(self) -> str:
        """Calculate test execution time, format: 0h4m"""
        try:
            total_seconds = self.test_time
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"
        except Exception as e:
            logger.LogErr(f"Failed to calculate test hours: {str(e)}")
            return "0h0m"
    
    @staticmethod
    def get_disk_type_name(disk_type_value: int) -> str:
        """
        Return disk type name based on disk_type value
        
        Args:
            disk_type_value: Disk type value
            
        Returns:
            str: Disk type name
        """
        disk_type_map = {
            SmiCliDiskType.DISK_TYPE_HDD: "HDD",
            SmiCliDiskType.DISK_TYPE_SATA: "SATA",
            SmiCliDiskType.DISK_TYPE_NVME: "NVMe",
            SmiCliDiskType.DISK_TYPE_UFD: "USB Flash Drive",
            SmiCliDiskType.DISK_TYPE_SM2320: "SM2320",
            SmiCliDiskType.DISK_TYPE_UFD_NOT_SMI: "USB Flash Drive (Non-SMI)",
            SmiCliDiskType.DISK_TYPE_SATA_PWR_1: "SATA Power Board V1",
            SmiCliDiskType.DISK_TYPE_SATA_PWR_2: "SATA Power Board V2",
            SmiCliDiskType.DISK_TYPE_PCIE_PWR_1: "PCIe Power Board V1",
            SmiCliDiskType.DISK_TYPE_PCIE_PWR_2: "PCIe Power Board V2"
        }
        return disk_type_map.get(disk_type_value, f"Unknown (0x{disk_type_value:X})")
    
    @staticmethod
    def get_protocol_type_name(protocol_type_value: int) -> str:
        """
        Return protocol type name based on protocol_type value
        
        Args:
            protocol_type_value: Protocol type value
            
        Returns:
            str: Protocol type name
        """
        protocol_type_map = {
            SmiCliProtocolType.PROTOCOL_TYPE_ATA_OVER_ATA: "ATA over ATA",
            SmiCliProtocolType.PROTOCOL_TYPE_ATA_OVER_USB: "ATA over USB",
            SmiCliProtocolType.PROTOCOL_TYPE_ATA_OVER_CSMI: "ATA over CSMI",
            SmiCliProtocolType.PROTOCOL_TYPE_NVME_OVER_STORNVME: "NVMe over StorNVMe",
            SmiCliProtocolType.PROTOCOL_TYPE_NVME_OVER_SCSIMINIPORT: "NVMe over SCSI Miniport",
            SmiCliProtocolType.PROTOCOL_TYPE_NVME_OVER_IRST: "NVMe over iRST",
            SmiCliProtocolType.PROTOCOL_TYPE_SCSI: "SCSI"
        }
        return protocol_type_map.get(protocol_type_value, f"Unknown (0x{protocol_type_value:X})")
    
    @staticmethod
    def is_nvme_disk(disk_type_value: int) -> bool:
        """
        Determine if it's an NVMe disk
        
        Args:
            disk_type_value: Disk type value
            
        Returns:
            bool: Whether it's an NVMe disk
        """
        nvme_types = [SmiCliDiskType.DISK_TYPE_NVME]
        return disk_type_value in nvme_types
    
    @staticmethod
    def is_usb_disk(disk_type_value: int) -> bool:
        """
        Determine if it's a USB disk
        
        Args:
            disk_type_value: Disk type value
            
        Returns:
            bool: Whether it's a USB disk
        """
        usb_types = [
            SmiCliDiskType.DISK_TYPE_UFD,
            SmiCliDiskType.DISK_TYPE_SM2320,
            SmiCliDiskType.DISK_TYPE_UFD_NOT_SMI
        ]
        return disk_type_value in usb_types
    
    @staticmethod
    def is_power_board_disk(disk_type_value: int) -> bool:
        """
        Determine if it's a Power Board disk
        
        Args:
            disk_type_value: Disk type value
            
        Returns:
            bool: Whether it's a Power Board disk
        """
        power_board_types = [
            SmiCliDiskType.DISK_TYPE_SATA_PWR_1,
            SmiCliDiskType.DISK_TYPE_SATA_PWR_2,
            SmiCliDiskType.DISK_TYPE_PCIE_PWR_1,
            SmiCliDiskType.DISK_TYPE_PCIE_PWR_2
        ]
        return disk_type_value in power_board_types
    
    def generate_dut_info(self, smicli_path: str = ".\\bin\\SmiCli\\SmiCli2.exe", 
                         output_file: Optional[str] = None, 
                         work_dir: Optional[str] = None) -> bool:
        """
        Execute SmiCli2.exe to get DUT information and generate DUT_Info.ini
        
        Args:
            smicli_path (str): Path to SmiCli2.exe, default is ".\\bin\\SmiCli\\SmiCli2.exe"
            output_file (str): Output file name, default is "DUT_Info.ini" in testlog directory
            work_dir (str): Working directory, if None uses current directory
            
        Returns:
            bool: Returns True if execution succeeds, False if it fails
        """
        try:
            # Set working directory
            if work_dir is None:
                work_dir = os.getcwd()
            
            # Set default output file path (in testlog directory)
            if output_file is None:
                output_file = os.path.join(self.path, "DUT_Info.ini")
            
            # Ensure absolute paths are used
            if not os.path.isabs(smicli_path):
                smicli_path = os.path.join(work_dir, smicli_path)
            
            if not os.path.isabs(output_file):
                output_file = os.path.join(work_dir, output_file)
                
            # Check if SmiCli2.exe exists
            if not os.path.exists(smicli_path):
                error_msg = f"SmiCli2.exe not found: {smicli_path}"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
                
            # Ensure output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Build command
            command = [smicli_path, "--info", f"--outfile={output_file}"]
            
            logger.LogEvt(f"Executing command: {' '.join(command)}")
            logger.LogEvt(f"Working directory: {work_dir}")
            
            # Execute command and wait for completion
            result = subprocess.run(
                command,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            logger.LogEvt(f"Return code: {result.returncode}")
            if result.stderr:
                logger.LogErr(f"Error output: {result.stderr}")
                
            if result.returncode == 0:
                # Wait for file to be completely written
                time.sleep(2)
                
                if os.path.exists(output_file):
                    try:
                        # Read file content and check
                        content = self._read_file_with_fallback_encoding(output_file)
                        if content:
                            logger.LogEvt(f"File content length: {len(content)}")
                            
                            # Check if it contains basic information structure
                            if '[info]' in content or '[disk_' in content:
                                logger.LogEvt(f"SmiCli2 executed successfully, output file created: {output_file}")
                                return True
                            else:
                                error_msg = f"SmiCli2 completed but output file format is abnormal: {output_file}"
                                logger.LogErr(error_msg)
                                self.error_message = error_msg
                                return False
                        else:
                            error_msg = f"SmiCli2 completed but unable to read output file: {output_file}"
                            logger.LogErr(error_msg)
                            self.error_message = error_msg
                            return False
                    except Exception as e:
                        error_msg = f"SmiCli2 completed but error occurred while reading file: {str(e)}"
                        logger.LogErr(error_msg)
                        self.error_message = error_msg
                        return False
                else:
                    error_msg = f"SmiCli2 completed but output file not found: {output_file}"
                    logger.LogErr(error_msg)
                    self.error_message = error_msg
                    return False
            else:
                error_msg_detail = result.stderr.strip() if result.stderr else "Unknown error"
                error_msg = f"SmiCli2 execution failed (return code: {result.returncode}): {error_msg_detail}"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
                
        except subprocess.TimeoutExpired:
            error_msg = "SmiCli2 execution timeout (60 seconds)"
            logger.LogErr(error_msg)
            self.error_message = error_msg
            return False
        except FileNotFoundError:
            error_msg = f"SmiCli2.exe not found: {smicli_path}"
            logger.LogErr(error_msg)
            self.error_message = error_msg
            return False
        except Exception as e:
            error_msg = f"Error occurred while executing SmiCli2: {str(e)}"
            logger.LogErr(error_msg)
            self.error_message = error_msg
            return False
    
    def load_dut_info(self) -> bool:
        """
        Load DUT information from DUT_Info.ini file
        
        Returns:
            bool: Returns True if loading succeeds, False if it fails
        """
        try:
            # Set file paths
            dut_info_file = os.path.join(self.path, "DUT_Info.ini")  # In testlog directory
            config_file = os.path.join(".", "Config", "Config.json")  # Config folder in working directory
            
            # Check if DUT_Info.ini exists
            if not os.path.exists(dut_info_file):
                error_msg = f"Error: DUT_Info.ini file not found: {dut_info_file}"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
            
            # Check if Config.json exists
            if not os.path.exists(config_file):
                error_msg = f"Error: Config.json file not found: {config_file}"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
            
            # Read Config.json to get DiskType setting
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    disk_type_value = config_data.get("DUT_info", {}).get("DiskType")
                    
                    if disk_type_value is None:
                        error_msg = "Error: DUT_info.DiskType setting not found in Config.json"
                        logger.LogErr(error_msg)
                        self.error_message = error_msg
                        return False
                    
                    if disk_type_value not in [0, 1]:
                        error_msg = f"Error: Invalid DiskType value in Config.json: {disk_type_value}. Only 0 (PRIMARY) and 1 (SECONDARY) are supported."
                        logger.LogErr(error_msg)
                        self.error_message = error_msg
                        return False
                    
                    disk_type = DiskType.PRIMARY if disk_type_value == 0 else DiskType.SECONDARY
                    logger.LogEvt(f"Read DiskType from Config.json: {disk_type_value} ({disk_type.name})")
                    
            except json.JSONDecodeError as e:
                error_msg = f"Error: Config.json format error: {str(e)}"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
            except Exception as e:
                error_msg = f"Error: Failed to read Config.json: {str(e)}"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
            
            # Read DUT_Info.ini file content
            content = self._read_file_with_fallback_encoding(dut_info_file)
            if not content:
                error_msg = f"Error: Unable to read DUT_Info.ini file content"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
            
            # Parse file content
            config = configparser.ConfigParser()
            try:
                config.read_string(content)
            except Exception as e:
                error_msg = f"Error: Failed to parse DUT_Info.ini file: {str(e)}"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
            
            # Read system information from [info] section
            if config.has_section('info'):
                info_section = config['info']
                self.os = info_section.get('os', '')
                self.platform = info_section.get('platform', '')
                self.bios = info_section.get('bios', '')
                self.cpu = info_section.get('cpu', '')
                self.ram = info_section.get('ram', '')
                self.spor_board = info_section.get('spor_board', '')
                logger.LogEvt("Successfully loaded system information")
            else:
                logger.LogEvt("[info] section not found in DUT_Info.ini file, skipping system information loading")
            
            # Select disk based on DiskType
            selected_disk = self._select_disk_by_type(config, disk_type)
            
            if not selected_disk:
                error_msg = f"Error: Unable to find suitable {disk_type.name} disk"
                logger.LogErr(error_msg)
                self.error_message = error_msg
                return False
            
            disk_section, disk_id = selected_disk
            self.disk_number = disk_section.get('id', disk_id)
            self.sample_slot = disk_section.get('location', '')
            self.controller_driver = disk_section.get('driver_version', '')
            self.sample_capacity = disk_section.get('capacity', '')
            self.sample_firmware = disk_section.get('fw', '')
            self.aspm = disk_section.get('aspm', '')  # Fixed: Ensure it's aspm
            
            # Get filesystem information
            drive_letters = disk_section.get('drive_letters', '')
            if drive_letters:
                filesystem_result = self._get_filesystem_type(drive_letters)
                if filesystem_result[0]:  # Success
                    self.sample_filesystem = filesystem_result[1]
                else:  # Failure
                    logger.LogEvt(f"Failed to query filesystem, using Unknown: {filesystem_result[1]}")
                    self.sample_filesystem = "Unknown"
            else:
                logger.LogEvt("Selected disk has no drive_letters information, using Unknown")
                self.sample_filesystem = "Unknown"
            
            logger.LogEvt(f"Successfully loaded DUT information (selected disk: disk_{disk_id})")
            return True
            
        except Exception as e:
            error_msg = f"Error: Unexpected error occurred while loading DUT information: {str(e)}"
            logger.LogErr(error_msg)
            self.error_message = error_msg
            return False
    
    def load_from_existing_runcard(self) -> bool:
        """
        Load test status from existing RunCard.ini (for data recovery after reboot)
        
        Returns:
            bool: Returns True if loading succeeds, False if it fails
        """
        try:
            runcard_file = os.path.join(self.path, "Runcard.ini")
            
            # Check if file exists
            if not os.path.exists(runcard_file):
                logger.LogEvt("Existing RunCard.ini file not found, proceeding with normal initialization")
                return False
            
            logger.LogEvt(f"Found existing RunCard.ini, starting to reload test status: {runcard_file}")
            
            # Read file content
            content = self._read_file_with_fallback_encoding(runcard_file)
            if not content:
                logger.LogEvt("Unable to read RunCard.ini file content, proceeding with normal initialization")
                return False
            
            # Parse INI file
            config = configparser.ConfigParser()
            config.optionxform = str  # Preserve case
            
            try:
                config.read_string(content)
            except Exception as e:
                logger.LogEvt(f"Failed to parse RunCard.ini: {str(e)}, proceeding with normal initialization")
                return False
            
            # Check if Test Status section exists
            if not config.has_section('Test Status'):
                logger.LogEvt("[Test Status] section not found in RunCard.ini, proceeding with normal initialization")
                return False
            
            status_section = config['Test Status']
            
            # Preserve dynamic information (unchanged after reload)
            self.disk_number = status_section.get('Disk Number', '')
            try:
                self.test_cycle = int(status_section.get('Test Cycle', '-1'))
            except ValueError:
                self.test_cycle = -1
            
            # Preserve autoit_version if it exists in INI, otherwise keep current value
            saved_autoit_version = status_section.get('AutoitVersion', '')
            if saved_autoit_version:
                self.autoit_version = saved_autoit_version
            # If saved version is empty and we have constructor parameters, regenerate
            elif not self.autoit_version and self.test_case and self.script_version:
                self.autoit_version = f"{self.test_case}_v{self.script_version}"
                logger.LogEvt(f"Regenerated AutoIt version during reload: {self.autoit_version}")
            
            # Note: test_case and script_version are not reloaded as they are provided during initialization
            
            # Reload start time
            start_time_str = status_section.get('Start Time', '')
            if start_time_str:
                try:
                    self._start_time = datetime.strptime(start_time_str, "%Y/%m/%d %H:%M:%S")
                    logger.LogEvt(f"Reloaded start time: {start_time_str}")
                except ValueError:
                    logger.LogEvt(f"Start time format error: {start_time_str}, using current time")
                    self._start_time = datetime.now()
            
            # Handle test result status
            test_result = status_section.get('Test Result', TestResult.ONGOING.value)
            if test_result in [TestResult.PASS.value, TestResult.FAIL.value, TestResult.INTERRUPT.value]:
                # If test has ended, reset to Ongoing to continue testing
                self.test_result = TestResult.ONGOING.value
                logger.LogEvt(f"Detected ended test status ({test_result}), reset to Ongoing to continue testing")
            else:
                self.test_result = test_result
            
            # Update end time to current time
            self._end_time = datetime.now()
            logger.LogEvt(f"Updated end time to current time: {self.end_time}")
            
            # Reload system information (static information)
            self.os = status_section.get('OS', '')
            self.platform = status_section.get('Platform', '')
            self.bios = status_section.get('BIOS', '')
            self.cpu = status_section.get('CPU', '')
            self.ram = status_section.get('RAM', '')
            self.spor_board = status_section.get('SPOR Board', '')
            
            # Reload disk information
            self.aspm = status_section.get('ASPM', '')  # Fixed: Ensure it's ASPM
            self.sample_capacity = status_section.get('Sample Capacity', '')
            self.controller_driver = status_section.get('Controller Driver', '')
            self.sample_firmware = status_section.get('Sample Firmware', '')
            self.sample_slot = status_section.get('Sample Slot', '')
            self.sample_filesystem = status_section.get('Sample FileSystem', '')
            
            # Reset error message
            self.error_message = "No Error"
            
            logger.LogEvt("Successfully reloaded test status")
            logger.LogEvt(f"Reload info - Test cycle: {self.test_cycle}, AutoIt version: {self.autoit_version}")
            logger.LogEvt(f"Reload info - Test time: {self.test_time} seconds ({self.test_hour})")
            
            return True
            
        except Exception as e:
            error_msg = f"Error occurred while reloading RunCard.ini: {str(e)}"
            logger.LogErr(error_msg)
            self.error_message = error_msg
            return False
    
    def initialize_with_reload(self) -> dict:
        """
        Integrate initialization and reload logic
        
        Returns:
            dict: Dictionary containing initialization results
            {
                'reloaded': bool,           # Whether successfully reloaded
                'dut_info_loaded': bool,    # Whether DUT info needs to be loaded
                'status': str               # Status description
            }
        """
        try:
            logger.LogEvt("Starting integrated initialization and reload process")
            
            # Attempt to reload existing status
            reloaded = self.load_from_existing_runcard()
            
            if reloaded:
                # Reload successful, check if DUT info needs updating
                dut_info_file = os.path.join(self.path, "DUT_Info.ini")
                
                if os.path.exists(dut_info_file):
                    # DUT_Info.ini exists, reload to update hardware info
                    logger.LogEvt("Reload mode: Found DUT_Info.ini, updating hardware info")
                    dut_loaded = self.load_dut_info()
                    
                    result = {
                        'reloaded': True,
                        'dut_info_loaded': dut_loaded,
                        'status': 'reloaded_with_dut_update'
                    }
                else:
                    # DUT_Info.ini doesn't exist, keep reloaded info
                    logger.LogEvt("Reload mode: DUT_Info.ini not found, keeping reloaded hardware info")
                    
                    result = {
                        'reloaded': True,
                        'dut_info_loaded': False,
                        'status': 'reloaded_without_dut'
                    }
            else:
                # Reload failed, proceed with normal initialization
                logger.LogEvt("Reload failed, proceeding with normal initialization")
                
                result = {
                    'reloaded': False,
                    'dut_info_loaded': False,
                    'status': 'normal_initialization'
                }
            
            # Save reload result for subsequent queries
            self._last_reload_result = result
            return result
            
        except Exception as e:
            error_msg = f"Error occurred in integrated initialization process: {str(e)}"
            logger.LogErr(error_msg)
            self.error_message = error_msg
            
            result = {
                'reloaded': False,
                'dut_info_loaded': False,
                'status': 'initialization_error'
            }
            self._last_reload_result = result
            return result
    
    def is_test_resumable(self) -> bool:
        """
        Check if test can continue execution (used to determine if start_test needs to be called)
        
        Returns:
            bool: Returns True if test can continue, False if it needs to restart
        """
        # If test result is Ongoing, it means it can continue
        if self.test_result == TestResult.ONGOING.value:
            # Check if there's valid start time and AutoIt version
            if self.autoit_version and self._start_time:
                logger.LogEvt("Detected resumable test status")
                return True
        
        logger.LogEvt("Detected test status that needs restart")
        return False
    
    def get_reload_summary(self) -> str:
        """
        Get reload status summary (for logging or display)
        
        Returns:
            str: Reload status summary
        """
        if hasattr(self, '_last_reload_result') and self._last_reload_result:
            result = self._last_reload_result
            
            if result['reloaded']:
                summary = f"Successfully reloaded test status\n"
                summary += f"  - Start time: {self.start_time}\n"
                summary += f"  - Test cycle: {self.test_cycle}\n"
                summary += f"  - AutoIt version: {self.autoit_version}\n"
                summary += f"  - Executed time: {self.test_time} seconds ({self.test_hour})\n"
                summary += f"  - DUT info: {'Updated' if result['dut_info_loaded'] else 'Using reloaded data'}"
            else:
                summary = "○ No reloadable status found, proceeding with normal initialization"
                
            return summary
        else:
            return "Reload check not yet executed"
    
    def _select_disk_by_type(self, config: configparser.ConfigParser, disk_type: DiskType) -> Optional[Tuple]:
        """
        Select appropriate disk based on disk type
        
        Args:
            config: Configuration parser object
            disk_type: Disk type
            
        Returns:
            tuple: (disk_section, disk_id) or None
        """
        if disk_type == DiskType.PRIMARY:
            # Primary - Find disk with drive_letters=C
            logger.LogEvt("Looking for Primary disk (drive_letters=C)")
            for section_name in config.sections():
                if section_name.startswith('disk_'):
                    disk_section = config[section_name]
                    drive_letters = disk_section.get('drive_letters', '')
                    
                    if 'C' in drive_letters.upper():
                        disk_id = section_name.replace('disk_', '')
                        logger.LogEvt(f"Found Primary disk: {section_name}")
                        return (disk_section, disk_id)
        
        elif disk_type == DiskType.SECONDARY:
            # Secondary - Find disks other than C drive, exclude USB and Power Board, prioritize NVMe
            logger.LogEvt("Looking for Secondary disk (non drive_letters=C, excluding USB and Power Board)")
            
            # First round: Look for NVMe disks
            for section_name in config.sections():
                if section_name.startswith('disk_'):
                    disk_section = config[section_name]
                    drive_letters = disk_section.get('drive_letters', '')
                    
                    # Exclude C drive
                    if 'C' in drive_letters.upper():
                        continue
                    
                    # Check disk type
                    try:
                        disk_type_value = int(disk_section.get('disk_type', '0'))
                    except ValueError:
                        continue
                    
                    # Exclude USB and Power Board
                    if self.is_usb_disk(disk_type_value) or self.is_power_board_disk(disk_type_value):
                        logger.LogEvt(f"Skipping {section_name}: {self.get_disk_type_name(disk_type_value)}")
                        continue
                    
                    # Prioritize NVMe
                    if self.is_nvme_disk(disk_type_value):
                        disk_id = section_name.replace('disk_', '')
                        logger.LogEvt(f"Found Secondary NVMe disk: {section_name} ({self.get_disk_type_name(disk_type_value)})")
                        return (disk_section, disk_id)
            
            # Second round: Look for other suitable disks
            for section_name in config.sections():
                if section_name.startswith('disk_'):
                    disk_section = config[section_name]
                    drive_letters = disk_section.get('drive_letters', '')
                    
                    # Exclude C drive
                    if 'C' in drive_letters.upper():
                        continue
                    
                    # Check disk type
                    try:
                        disk_type_value = int(disk_section.get('disk_type', '0'))
                    except ValueError:
                        continue
                    
                    # Exclude USB and Power Board
                    if self.is_usb_disk(disk_type_value) or self.is_power_board_disk(disk_type_value):
                        continue
                    
                    disk_id = section_name.replace('disk_', '')
                    logger.LogEvt(f"Found Secondary disk: {section_name} ({self.get_disk_type_name(disk_type_value)})")
                    return (disk_section, disk_id)
        
        return None
    
    def _get_filesystem_type(self, drive_letter: str) -> Tuple[bool, str]:
        """
        Get filesystem type of drive
        
        Args:
            drive_letter: Drive letter
            
        Returns:
            tuple: (Success/Failure, Filesystem type or error message)
        """
        try:
            if not WIN32_AVAILABLE:
                return (False, "win32api module not available")
            
            drive_path = f"{drive_letter}:\\"
            volume_info = win32api.GetVolumeInformation(drive_path)
            filesystem_type = volume_info[4]  # Filesystem name
            logger.LogEvt(f"Successfully got {drive_letter} drive filesystem: {filesystem_type}")
            return (True, filesystem_type)
            
        except Exception as e:
            error_msg = f"Failed to query {drive_letter} drive filesystem: {str(e)}"
            logger.LogErr(error_msg)
            return (False, error_msg)
    
    def _read_file_with_fallback_encoding(self, file_path: str) -> Optional[str]:
        """
        Try to read file using multiple encodings
        
        Args:
            file_path: File path
            
        Returns:
            str: File content, returns None if reading fails
        """
        encodings = ['utf-8', 'big5', 'gbk', 'cp950', 'latin1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    logger.LogEvt(f"Successfully read file using {encoding} encoding")
                    return content
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                logger.LogErr(f"Failed to read file: {str(e)}")
                break
        
        return None
        
    def save_to_file(self, filename: str = "Runcard", file_format: RuncardFormat = RuncardFormat.INI, max_retries: int = 3) -> bool:
        """
        Save runcard information to file
        
        Args:
            filename: File name (without extension)
            file_format: File format
            max_retries: Maximum retry attempts
            
        Returns:
            bool: Returns True if saving succeeds, False if it fails
        """
        try:
            if self.test_result == TestResult.ONGOING.value:
                self._end_time = datetime.now()
                
            # Ensure output directory exists
            if not os.path.exists(self.path):
                os.makedirs(self.path)
            
            file_path = ""
            if file_format == RuncardFormat.INI:
                file_path = os.path.join(self.path, f"{filename}.ini")
            elif file_format == RuncardFormat.JSON:
                file_path = os.path.join(self.path, f"{filename}.json")
            
            # 重試機制
            for attempt in range(max_retries):
                try:
                    if file_format == RuncardFormat.INI:
                        return self._save_to_ini(file_path)
                    elif file_format == RuncardFormat.JSON:
                        return self._save_to_json(file_path)
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)  # 等待 0.5 秒後重試
                        continue
                    else:
                        # 所有重試都失敗，但不寫入 error_message，只記錄 log
                        logger.LogErr(f"Failed to save file after {max_retries} retries: Permission denied")
                        return False
            
        except Exception as e:
            error_msg = f"Error occurred while saving file: {str(e)}"
            logger.LogErr(error_msg)
            if self.error_message == "No Error":
                self.error_message = error_msg
            return False
        
        return False


    def _save_to_ini(self, file_path: str) -> bool:
        """
        Save as INI format
        
        Args:
            file_path: File path
            
        Returns:
            bool: Returns True if saving succeeds
            
        Raises:
            PermissionError: When file is locked or permission denied
        """
        config = configparser.ConfigParser()
        # Set optionxform to str to preserve original case
        config.optionxform = str
        config.add_section('Test Status')
        
        # Create attribute mapping dictionary (using title case format)
        attributes = {
            'Disk Number': str(self.disk_number),
            'Start Time': self.start_time,
            'End Time': self.end_time,
            'Test Result': self.test_result,
            'Test Time': str(self.test_time),
            'Test Hour': self.test_hour,
            'Test Cycle': str(self.test_cycle),
            'Error Message': self.error_message,
            'Sample Slot': self.sample_slot,
            'Controller Driver': self.controller_driver,
            'BIOS': self.bios,
            'OS': self.os,
            'SPOR Board': self.spor_board,
            'ASPM': self.aspm,
            'Sample FileSystem': self.sample_filesystem,
            'Sample Capacity': self.sample_capacity,
            'Sample Firmware': self.sample_firmware,
            'Platform': self.platform,
            'CPU': self.cpu,
            'RAM': self.ram,
            'AutoItVersion': self.autoit_version
        }
        
        # Write all attributes (including empty strings)
        for key, value in attributes.items():
            config.set('Test Status', key, str(value) if value is not None else '')
        
        # Write to file - let PermissionError propagate to caller for retry
        with open(file_path, 'w', encoding='utf-8') as f:
            config.write(f, space_around_delimiters=False)
        
        # logger.LogEvt(f"Successfully saved runcard to: {file_path}")
        return True


    def _save_to_json(self, file_path: str) -> bool:
        """
        Save as JSON format
        
        Args:
            file_path: File path
            
        Returns:
            bool: Returns True if saving succeeds
        """
        try:
            data = {
                attr: getattr(self, attr) 
                for attr in dir(self) 
                if not attr.startswith('_') and not callable(getattr(self, attr))
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            # logger.LogEvt(f"Successfully saved runcard to: {file_path}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save JSON file: {str(e)}"
            logger.LogErr(error_msg)
            if self.error_message == "No Error":
                self.error_message = error_msg
            return False

    def reload_and_update(self, test_cycle: int = None, filename: str = "RunCard", 
                        file_format: RuncardFormat = RuncardFormat.INI) -> dict:
        """
        重新載入測試狀態並更新測試週期
        
        Args:
            test_cycle: 測試週期數，如果為 None 則不更新
            filename: 儲存檔案名稱
            file_format: 儲存格式
            
        Returns:
            dict: initialize_with_reload 的返回結果
        """
        # 重新載入測試狀態
        reload_result = self.initialize_with_reload()
        
        # 如果提供了 test_cycle，更新測試狀態
        if test_cycle is not None:
            self.update_test_status(test_cycle=test_cycle)
        
        # 儲存到檔案
        self.save_to_file(filename, file_format)
        
        return reload_result

    def update_test_status(self, **kwargs) -> None:
        """
        Update test status
        
        Args:
            **kwargs: Attributes and values to update
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.LogEvt(f"Updated test status: {key} = {value}")
            else:
                logger.LogEvt(f"Warning: Non-existent attribute: {key}")
    
    def start_test(self, autoit_version: str = "", auto_setup: bool = True, smicli_path: str = None) -> None:
        """
        Start test
        
        Args:
            autoit_version: AutoIt version. If empty, will auto-generate from test_case and script_version
            auto_setup: Whether to automatically execute generate_dut_info and load_dut_info, default is True
            smicli_path: Path to SmiCli2.exe. If None, uses default path ".\\bin\\SmiCli\\SmiCli2.exe"
            
        Raises:
            Exception: When generate_dut_info or load_dut_info fails
        """
        if auto_setup:
            # Execute generate_dut_info and check result
            if smicli_path:
                result = self.generate_dut_info(smicli_path=smicli_path)
            else:
                result = self.generate_dut_info()
            if not result:
                error_msg = 'generate_dut_info fail'
                logger.LogErr(error_msg)
                raise Exception(error_msg)
            
            # Execute load_dut_info and check result
            result = self.load_dut_info()
            if not result:
                error_msg = 'load_dut_info fail'
                logger.LogErr(error_msg)
                raise Exception(error_msg)
            
        # Set both start and end time to current time simultaneously to avoid time inconsistency
        current_time = datetime.now()
        self._start_time = current_time
        self._end_time = current_time
        
        self.test_result = TestResult.ONGOING.value
        self.error_message = "No Error"
        
        # Auto-generate autoit_version if not provided and we have test case and script version
        if not autoit_version and self.test_case and self.script_version:
            autoit_version = f"{self.test_case}_v{self.script_version}"
        
        self.autoit_version = autoit_version
        logger.LogEvt(f"Test started, AutoIt version: {autoit_version}")
        logger.LogEvt(f"Set start time and end time: {current_time.strftime('%Y/%m/%d %H:%M:%S')}")
        
        if self.test_case:
            logger.LogEvt(f"Test case: {self.test_case}")
        if self.script_version:
            logger.LogEvt(f"Script version: {self.script_version}")
        self.save_to_file()
    
    def end_test(self, result: str = TestResult.PASS.value, error_message: str = "No Error") -> None:
        """
        End test
        
        Args:
            result: Test result (PASS, FAIL, Interrupt, Ongoing)
            error_message: Error message
        """
        current_time = datetime.now()
        
        # Verify time logic
        if current_time < self._start_time:
            logger.LogErr(f"Detected time anomaly: End time {current_time} is earlier than start time {self._start_time}")
            logger.LogErr("Setting end time to start time to avoid negative values")
            self._end_time = self._start_time
        else:
            self._end_time = current_time
        
        self.test_result = result
        self.error_message = error_message
        
        logger.LogEvt(f"Test ended: {result}")
        logger.LogEvt(f"End time: {self.end_time}")
        logger.LogEvt(f"Test time: {self.test_time} seconds ({self.test_hour})")
        
        if error_message != "No Error":
            logger.LogErr(f"Error message: {error_message}")
        self.save_to_file()

# Test script
if __name__ == "__main__":
    print("=== RunCard Test Script ===")
    
    # Create runcard object
    print("1. Creating Runcard object...")
    runcard = Runcard("./testlog")
    print(f"   Test path: {runcard.path}")
    
    # Execute integrated initialization and reload
    print("\n2. Checking reload requirements...")
    reload_result = runcard.initialize_with_reload()
    
    if reload_result['reloaded']:
        print("Found existing test status, reloaded")
        print(runcard.get_reload_summary())
        
        # If needed, load DUT information
        if not reload_result['dut_info_loaded']:
            print("\nLoading DUT information...")
            generate_dut = input("Do you want to execute SmiCli2 to generate DUT_Info.ini? (y/n): ").lower() == 'y'
            if generate_dut and runcard.generate_dut_info():
                runcard.load_dut_info()
        
        # Check if test can continue
        if runcard.is_test_resumable():
            print("Test will continue from interruption point...")
            # No need to call start_test(), continue with test logic directly
        else:
            print("Need to restart test...")
            runcard.start_test("STC-1735")
            
    else:
        print("○ Starting new test")
        
        # Option: Whether to execute SmiCli2 to generate DUT_Info.ini
        generate_dut = input("\nDo you want to execute SmiCli2 to generate DUT_Info.ini? (y/n): ").lower() == 'y'
        
        if generate_dut:
            print("\n3. Executing SmiCli2 to generate DUT_Info.ini...")
            if runcard.generate_dut_info():
                print("   DUT_Info.ini generated successfully")
            else:
                print(f"   DUT_Info.ini generation failed: {runcard.error_message}")
                print("   Continuing to test other functions...")
        
        # Create test Config.json
        print("\n4. Creating test Config.json...")
        config_dir = "./Config"
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        config_file = os.path.join(config_dir, "Config.json")
        test_config = {
            "DUT_info": {
                "DiskType": 0  # Primary disk (C drive)
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, indent=2)
        print(f"   Config.json created: {config_file}")
        
        # Load DUT information
        print("\n5. Loading DUT information...")
        if runcard.load_dut_info():
            print("   DUT information loaded successfully")
            print(f"   OS: {runcard.os}")
            print(f"   Platform: {runcard.platform}")
            print(f"   CPU: {runcard.cpu}")
            print(f"   RAM: {runcard.ram}")
            print(f"   Selected disk: {runcard.disk_number}")
            print(f"   Filesystem: {runcard.sample_filesystem}")
        else:
            print(f"   Failed to load DUT information: {runcard.error_message}")
            print("   Using simulated data to continue testing...")
            # Set simulated data
            runcard.os = "Windows 11 Pro 64-bit"
            runcard.platform = "Test Platform"
            runcard.cpu = "Test CPU"
            runcard.ram = "16.00GB"
            runcard.disk_number = "0"
            runcard.sample_filesystem = "NTFS"
            runcard.sample_capacity = "500GB"
            runcard.aspm = "Enabled"
        
        # Start test
        print("\n6. Starting test...")
        runcard.start_test("STC-1735")
    
    print(f"   Test start time: {runcard.start_time}")
    print(f"   Current end time: {runcard.end_time}")
    print(f"   Current test time: {runcard.test_time} seconds")
    
    # Simulate test execution time
    print("   Simulating test execution...")
    import time
    time.sleep(5)  # Simulate 5 seconds of test time
    
    # Update test status
    print("\n7. Updating test status...")
    runcard.update_test_status(test_cycle=1)
    print("   Test status updated")
    
    # Test disk type query function
    print("\n8. Testing disk type query function...")
    test_disk_types = [0x140, 0x180, 0x200, 0x202, 0x999]
    for disk_type in test_disk_types:
        type_name = runcard.get_disk_type_name(disk_type)
        is_nvme = runcard.is_nvme_disk(disk_type)
        is_usb = runcard.is_usb_disk(disk_type)
        is_power_board = runcard.is_power_board_disk(disk_type)
        print(f"   Disk type 0x{disk_type:X}: {type_name} (NVMe:{is_nvme}, USB:{is_usb}, PowerBoard:{is_power_board})")
    
    # End test
    print("\n9. Ending test...")
    runcard.end_test(TestResult.PASS.value, "No Error")
    print(f"   Test end time: {runcard.end_time}")
    print(f"   Test time: {runcard.test_time} seconds")
    print(f"   Test hours: {runcard.test_hour}")
    print(f"   Test result: {runcard.test_result}")
    
    # Save runcard
    print("\n10. Saving RunCard.ini...")
    if runcard.save_to_file("Runcard", RuncardFormat.INI):
        print("   RunCard.ini saved successfully")
        runcard_file = os.path.join(runcard.path, "Runcard.ini")
        print(f"   File location: {runcard_file}")
        
        # Display file content
        if os.path.exists(runcard_file):
            print("\n   File content:")
            with open(runcard_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print("   " + content.replace('\n', '\n   '))
    else:
        print(f"   Failed to save RunCard.ini: {runcard.error_message}")
    
    # Test completed
    print("\n=== Test Completed ===")
    print("You can check the following files:")
    print(f"- Log file: ./log/log.txt")
    if os.path.exists("./Config/Config.json"):
        print(f"- Config file: ./Config/Config.json")
    if os.path.exists(os.path.join(runcard.path, "Runcard.ini")):
        print(f"- Runcard file: {os.path.join(runcard.path, 'Runcard.ini')}")
    
    print("\nReload test demonstration:")
    print("Run this script again, it will automatically detect and reload existing RunCard.ini")
    
    # Disk type table demonstration
    print("\n=== SmiCli Disk Type Table ===")
    disk_types = [
        (SmiCliDiskType.DISK_TYPE_HDD, "HDD"),
        (SmiCliDiskType.DISK_TYPE_SATA, "SATA"),
        (SmiCliDiskType.DISK_TYPE_NVME, "NVMe"),
        (SmiCliDiskType.DISK_TYPE_UFD, "USB Flash Drive"),
        (SmiCliDiskType.DISK_TYPE_SM2320, "SM2320"),
        (SmiCliDiskType.DISK_TYPE_UFD_NOT_SMI, "USB Flash Drive (Non-SMI)"),
        (SmiCliDiskType.DISK_TYPE_SATA_PWR_1, "SATA Power Board V1"),
        (SmiCliDiskType.DISK_TYPE_SATA_PWR_2, "SATA Power Board V2"),
        (SmiCliDiskType.DISK_TYPE_PCIE_PWR_1, "PCIe Power Board V1"),
        (SmiCliDiskType.DISK_TYPE_PCIE_PWR_2, "PCIe Power Board V2")
    ]
    
    for disk_type_value, description in disk_types:
        print(f"0x{disk_type_value:X} ({disk_type_value}): {description}")