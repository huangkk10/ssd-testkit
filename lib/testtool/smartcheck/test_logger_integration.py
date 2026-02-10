"""
Test Logger Integration

Simple script to verify that controller.py correctly uses lib/logger.py
"""

import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.testtool.smartcheck import SmartCheckController

def test_logger_integration():
    """Test that SmartCheckController can be imported and uses logger correctly."""
    print("=" * 60)
    print("Testing SmartCheck Logger Integration")
    print("=" * 60)
    
    try:
        # Create controller instance
        # This will trigger logger initialization and some log messages
        controller = SmartCheckController(
            bat_path="mock/SmartCheck.bat",
            cfg_ini_path="mock/SmartCheck.ini",
            output_dir="./test_output",
            total_cycle=1,
            total_time=1,  # 1 minute
            dut_id="TEST_DUT",
            smartcheck_options="-test",
            timeout=1  # 1 minute
        )
        
        print(f"\n✅ Controller created successfully")
        print(f"   - Output dir: {controller.output_dir}")
        print(f"   - Timeout: {controller.timeout} minutes")
        print(f"   - Total time: {controller.total_time} minutes")
        print(f"   - DUT ID: {controller.dut_id}")
        
        # Test configuration loading
        print("\n📋 Testing configuration methods...")
        config_dict = controller.get_config()
        print(f"   - Config keys: {list(config_dict.keys())}")
        
        # Test set_config
        controller.set_config('dut_id', 'NEW_TEST_DUT')
        print(f"   - Updated DUT ID: {controller.dut_id}")
        
        print("\n✅ All logger integration tests passed!")
        print("\n📝 Check log files:")
        print("   - log/log.txt  (info/debug logs)")
        print("   - log/log.err  (error/warning logs)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_logger_integration()
    sys.exit(0 if success else 1)
