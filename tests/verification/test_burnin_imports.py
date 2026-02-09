"""
Test Burnin Import Verification
Verify that the RunCard integration in test_burnin.py can be imported correctly
"""
import sys
from pathlib import Path

# Add project path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

def test_imports():
    """Test all imports"""
    print("=" * 60)
    print("Verifying imports for test_burnin.py")
    print("=" * 60)
    
    try:
        # Switch to the test directory
        test_dir = Path(__file__).parent.parent / "integration/client_pcie_lenovo_storagedv/stc1685_burnin"
        
        # Test imports
        from lib.testtool import RunCard as RC
        print("✓ RunCard imported successfully")
        
        from lib.testtool import BurnIN
        print("✓ BurnIN imported successfully")
        
        import lib.testtool.DiskPrd as DiskPrd
        print("✓ DiskPrd imported successfully")
        
        import lib.testtool.SmiSmartCheck as SmiSmartCheck
        print("✓ SmiSmartCheck imported successfully")
        
        import lib.testtool.CDI as CDI
        print("✓ CDI imported successfully")
        
        import lib.logger as logger
        print("✓ logger imported successfully")
        
        from framework.base_test import BaseTestCase
        print("✓ BaseTestCase imported successfully")
        
        from framework.decorators import step
        print("✓ step decorator imported successfully")
        
        # Check RunCard enums
        print("\nCheck RunCard enums:")
        print(f"  TestResult.PASS = {RC.TestResult.PASS.value}")
        print(f"  TestResult.FAIL = {RC.TestResult.FAIL.value}")
        
        # Check SmiCli path
        print("\nCheck SmiCli path:")
        smicli_path = test_dir / "bin/SmiWinTools/bin/x64/SmiCli2.exe"
        print(f"  Path: {smicli_path}")
        print(f"  Exists: {smicli_path.exists()}")
        
        print("\n" + "=" * 60)
        print("✓ All import checks passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
