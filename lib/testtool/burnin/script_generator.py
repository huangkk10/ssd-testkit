"""
BurnIN Script Generator

This module provides script generation utilities for BurnIN.bits files.
"""

import os
from typing import Optional
from pathlib import Path


class BurnInScriptGenerator:
    """
    BurnIN script generator for .bits files.
    
    This class handles generation of BurnIN test scripts with
    various configurations and test modes.
    
    All methods are static - no need to instantiate this class.
    
    Example:
        >>> script_path = BurnInScriptGenerator.generate_disk_test_script(
        ...     config_file_path="./test.bitcfg",
        ...     log_path="./test.log",
        ...     duration_minutes=60,
        ...     drive_letter="D",
        ...     output_path="./test.bits"
        ... )
        >>> print(script_path)
        ./test.bits
    """
    
    @staticmethod
    def generate_disk_test_script(
        config_file_path: str,
        log_path: str,
        duration_minutes: int,
        drive_letter: str,
        output_path: str
    ) -> str:
        """
        Generate BurnIN disk test script.
        
        Creates a .bits script file for running disk tests on a specific drive.
        
        Args:
            config_file_path: Path to .bitcfg file
            log_path: Path for log output
            duration_minutes: Test duration in minutes
            drive_letter: Drive letter to test (e.g., 'D')
            output_path: Path to save generated script
        
        Returns:
            str: Path to generated script file (same as output_path)
        
        Raises:
            ValueError: If parameters are invalid
            OSError: If file cannot be written
        
        Example:
            >>> script = BurnInScriptGenerator.generate_disk_test_script(
            ...     config_file_path="./Config/test.bitcfg",
            ...     log_path="./testlog/burnin.log",
            ...     duration_minutes=60,
            ...     drive_letter="D",
            ...     output_path="./Config/test.bits"
            ... )
        """
        # Validate inputs
        if not config_file_path:
            raise ValueError("config_file_path cannot be empty")
        if not log_path:
            raise ValueError("log_path cannot be empty")
        if duration_minutes < 0:
            raise ValueError("duration_minutes must be >= 0")
        if not drive_letter or len(drive_letter) != 1 or not drive_letter.isalpha():
            raise ValueError("drive_letter must be a single letter (A-Z)")
        if not output_path:
            raise ValueError("output_path cannot be empty")
        
        # Normalize drive letter to uppercase
        drive_letter = drive_letter.upper()
        
        # Get absolute paths
        abs_config_path = os.path.abspath(config_file_path)
        abs_log_path = os.path.abspath(log_path)
        
        # Generate script content
        script_content = f'''LOAD "{abs_config_path}"
SETLOG LOG yes Name "{abs_log_path}" TIME no REPORT text
SETDURATION {duration_minutes}
SETDISK DISK {drive_letter}:
RUN DISK
'''
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write script file
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(script_content)
        
        return output_path
    
    @staticmethod
    def generate_full_config_script(
        config_file_path: str,
        log_path: str,
        duration_minutes: Optional[int],
        output_path: str
    ) -> str:
        """
        Generate BurnIN full configuration test script.
        
        Creates a .bits script file for running full configuration tests
        (all tests defined in the .bitcfg file).
        
        Args:
            config_file_path: Path to .bitcfg file
            log_path: Path for log output
            duration_minutes: Test duration in minutes (None = indefinite)
            output_path: Path to save generated script
        
        Returns:
            str: Path to generated script file (same as output_path)
        
        Raises:
            ValueError: If parameters are invalid
            OSError: If file cannot be written
        
        Example:
            >>> # Indefinite duration
            >>> script = BurnInScriptGenerator.generate_full_config_script(
            ...     config_file_path="./Config/test.bitcfg",
            ...     log_path="./testlog/burnin.log",
            ...     duration_minutes=None,
            ...     output_path="./Config/test.bits"
            ... )
            
            >>> # Fixed duration
            >>> script = BurnInScriptGenerator.generate_full_config_script(
            ...     config_file_path="./Config/test.bitcfg",
            ...     log_path="./testlog/burnin.log",
            ...     duration_minutes=1440,
            ...     output_path="./Config/test.bits"
            ... )
        """
        # Validate inputs
        if not config_file_path:
            raise ValueError("config_file_path cannot be empty")
        if not log_path:
            raise ValueError("log_path cannot be empty")
        if duration_minutes is not None and duration_minutes < 0:
            raise ValueError("duration_minutes must be >= 0 or None")
        if not output_path:
            raise ValueError("output_path cannot be empty")
        
        # Get absolute paths
        abs_config_path = os.path.abspath(config_file_path)
        abs_log_path = os.path.abspath(log_path)
        
        # Generate script content
        if duration_minutes is None:
            script_content = f'''LOAD "{abs_config_path}"
SETLOG LOG yes Name "{abs_log_path}" TIME no REPORT text
RUN CONFIG
'''
        else:
            script_content = f'''LOAD "{abs_config_path}"
SETLOG LOG yes Name "{abs_log_path}" TIME no REPORT text
SETDURATION {duration_minutes}
RUN CONFIG
'''
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write script file
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(script_content)
        
        return output_path
    
    @staticmethod
    def generate_custom_script(
        script_content: str,
        output_path: str
    ) -> str:
        """
        Generate custom BurnIN script from provided content.
        
        Args:
            script_content: Custom script content
            output_path: Path to save generated script
        
        Returns:
            str: Path to generated script file (same as output_path)
        
        Raises:
            ValueError: If parameters are invalid
            OSError: If file cannot be written
        
        Example:
            >>> custom_content = '''LOAD "C:\\test.bitcfg"
            ... SETLOG LOG yes Name "C:\\test.log"
            ... RUN DISK
            ... '''
            >>> script = BurnInScriptGenerator.generate_custom_script(
            ...     script_content=custom_content,
            ...     output_path="./custom.bits"
            ... )
        """
        # Validate inputs
        if not script_content:
            raise ValueError("script_content cannot be empty")
        if not output_path:
            raise ValueError("output_path cannot be empty")
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write script file
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(script_content)
        
        return output_path
