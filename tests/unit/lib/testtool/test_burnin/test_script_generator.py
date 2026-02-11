"""
Unit tests for BurnIN script generator module.
"""

import pytest
import os
from lib.testtool.burnin.script_generator import BurnInScriptGenerator


class TestBurnInScriptGenerator:
    """Test suite for BurnInScriptGenerator class."""
    
    def test_generate_disk_test_script(self, temp_dir, temp_config_path, temp_log_path, temp_script_path):
        """Test generation of disk test script."""
        # Create dummy config file
        with open(temp_config_path, 'w') as f:
            f.write("# Test config")
        
        script_path = BurnInScriptGenerator.generate_disk_test_script(
            config_file_path=temp_config_path,
            log_path=temp_log_path,
            duration_minutes=60,
            drive_letter='D',
            output_path=temp_script_path
        )
        
        # Check that script was created
        assert os.path.exists(script_path)
        assert script_path == temp_script_path
        
        # Read and verify content
        with open(script_path, 'r') as f:
            content = f.read()
        
        assert 'LOAD' in content
        assert 'SETLOG' in content
        assert 'SETDURATION 60' in content
        assert 'SETDISK DISK D:' in content
        assert 'RUN DISK' in content
        assert temp_config_path in content or os.path.abspath(temp_config_path) in content
        assert temp_log_path in content or os.path.abspath(temp_log_path) in content
    
    def test_generate_disk_test_script_creates_directory(self, temp_dir):
        """Test that script generation creates output directory if needed."""
        nested_path = os.path.join(temp_dir, 'subdir', 'test.bits')
        config_path = os.path.join(temp_dir, 'test.bitcfg')
        log_path = os.path.join(temp_dir, 'test.log')
        
        # Create dummy config
        with open(config_path, 'w') as f:
            f.write("# Test")
        
        script_path = BurnInScriptGenerator.generate_disk_test_script(
            config_file_path=config_path,
            log_path=log_path,
            duration_minutes=60,
            drive_letter='D',
            output_path=nested_path
        )
        
        # Check that directory was created
        assert os.path.exists(os.path.dirname(nested_path))
        assert os.path.exists(script_path)
    
    def test_generate_disk_test_script_drive_letter_case(self, temp_dir, temp_config_path, temp_log_path):
        """Test that drive letter is normalized to uppercase."""
        script_path = os.path.join(temp_dir, 'test.bits')
        
        # Create dummy config
        with open(temp_config_path, 'w') as f:
            f.write("# Test")
        
        # Test with lowercase
        BurnInScriptGenerator.generate_disk_test_script(
            config_file_path=temp_config_path,
            log_path=temp_log_path,
            duration_minutes=60,
            drive_letter='d',  # lowercase
            output_path=script_path
        )
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Should be uppercase in script
        assert 'SETDISK DISK D:' in content
        assert 'SETDISK DISK d:' not in content
    
    def test_generate_disk_test_script_invalid_params(self, temp_dir):
        """Test validation of invalid parameters."""
        script_path = os.path.join(temp_dir, 'test.bits')
        config_path = os.path.join(temp_dir, 'test.bitcfg')
        log_path = os.path.join(temp_dir, 'test.log')
        
        # Empty config_file_path
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_disk_test_script(
                config_file_path='',
                log_path=log_path,
                duration_minutes=60,
                drive_letter='D',
                output_path=script_path
            )
        assert 'config_file_path' in str(exc_info.value)
        
        # Empty log_path
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_disk_test_script(
                config_file_path=config_path,
                log_path='',
                duration_minutes=60,
                drive_letter='D',
                output_path=script_path
            )
        assert 'log_path' in str(exc_info.value)
        
        # Negative duration
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_disk_test_script(
                config_file_path=config_path,
                log_path=log_path,
                duration_minutes=-1,
                drive_letter='D',
                output_path=script_path
            )
        assert 'duration_minutes' in str(exc_info.value)
        
        # Invalid drive letter
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_disk_test_script(
                config_file_path=config_path,
                log_path=log_path,
                duration_minutes=60,
                drive_letter='DD',
                output_path=script_path
            )
        assert 'drive_letter' in str(exc_info.value)
        
        # Empty output_path
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_disk_test_script(
                config_file_path=config_path,
                log_path=log_path,
                duration_minutes=60,
                drive_letter='D',
                output_path=''
            )
        assert 'output_path' in str(exc_info.value)
    
    def test_generate_full_config_script_with_duration(self, temp_dir, temp_config_path, temp_log_path, temp_script_path):
        """Test generation of full config script with duration."""
        # Create dummy config
        with open(temp_config_path, 'w') as f:
            f.write("# Test")
        
        script_path = BurnInScriptGenerator.generate_full_config_script(
            config_file_path=temp_config_path,
            log_path=temp_log_path,
            duration_minutes=1440,
            output_path=temp_script_path
        )
        
        assert os.path.exists(script_path)
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        assert 'LOAD' in content
        assert 'SETLOG' in content
        assert 'SETDURATION 1440' in content
        assert 'RUN CONFIG' in content
    
    def test_generate_full_config_script_without_duration(self, temp_dir, temp_config_path, temp_log_path, temp_script_path):
        """Test generation of full config script without duration."""
        # Create dummy config
        with open(temp_config_path, 'w') as f:
            f.write("# Test")
        
        script_path = BurnInScriptGenerator.generate_full_config_script(
            config_file_path=temp_config_path,
            log_path=temp_log_path,
            duration_minutes=None,
            output_path=temp_script_path
        )
        
        assert os.path.exists(script_path)
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        assert 'LOAD' in content
        assert 'SETLOG' in content
        assert 'SETDURATION' not in content
        assert 'RUN CONFIG' in content
    
    def test_generate_full_config_script_invalid_params(self, temp_dir):
        """Test validation of invalid parameters for full config script."""
        script_path = os.path.join(temp_dir, 'test.bits')
        config_path = os.path.join(temp_dir, 'test.bitcfg')
        log_path = os.path.join(temp_dir, 'test.log')
        
        # Negative duration (not None)
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_full_config_script(
                config_file_path=config_path,
                log_path=log_path,
                duration_minutes=-1,
                output_path=script_path
            )
        assert 'duration_minutes' in str(exc_info.value)
    
    def test_generate_custom_script(self, temp_dir, temp_script_path):
        """Test generation of custom script."""
        custom_content = '''LOAD "C:\\test.bitcfg"
SETLOG LOG yes Name "C:\\test.log"
SETDURATION 120
RUN DISK
'''
        
        script_path = BurnInScriptGenerator.generate_custom_script(
            script_content=custom_content,
            output_path=temp_script_path
        )
        
        assert os.path.exists(script_path)
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        assert content == custom_content
    
    def test_generate_custom_script_invalid_params(self, temp_dir):
        """Test validation of invalid parameters for custom script."""
        script_path = os.path.join(temp_dir, 'test.bits')
        
        # Empty content
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_custom_script(
                script_content='',
                output_path=script_path
            )
        assert 'script_content' in str(exc_info.value)
        
        # Empty output_path
        with pytest.raises(ValueError) as exc_info:
            BurnInScriptGenerator.generate_custom_script(
                script_content='LOAD "test.bitcfg"',
                output_path=''
            )
        assert 'output_path' in str(exc_info.value)
    
    def test_script_encoding(self, temp_dir, temp_config_path, temp_log_path, temp_script_path):
        """Test that scripts are written with UTF-8 encoding."""
        # Create dummy config
        with open(temp_config_path, 'w') as f:
            f.write("# Test")
        
        BurnInScriptGenerator.generate_disk_test_script(
            config_file_path=temp_config_path,
            log_path=temp_log_path,
            duration_minutes=60,
            drive_letter='D',
            output_path=temp_script_path
        )
        
        # Read with UTF-8 encoding
        with open(temp_script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert len(content) > 0
        assert 'RUN DISK' in content
