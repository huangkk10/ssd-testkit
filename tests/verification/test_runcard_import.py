"""
RunCard Import Verification Script
Verify that RunCard can be imported and initialized successfully
"""
import sys
from pathlib import Path

# Add path (from tests/verification/ back to project root)
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

def test_runcard_import():
    """Test RunCard import"""
    print("=" * 60)
    print("RunCard import verification test")
    print("=" * 60)
    
    try:
        from lib.testtool import RunCard as RC
        print("✓ RunCard module imported successfully")
        print(f"  Module location: {RC.__file__}")
        
        # Check that key classes exist
        print("\nChecking key classes:")
        classes_to_check = [
            ('Runcard', 'RunCard main class'),
            ('TestResult', 'Test result enum'),
            ('DiskType', 'Disk type enum'),
            ('RuncardFormat', 'RunCard format enum'),
        ]
        
        for class_name, desc in classes_to_check:
            if hasattr(RC, class_name):
                print(f"  ✓ {class_name} - {desc}")
            else:
                print(f"  ✗ {class_name} - 未找到")
                return False
        
        # Test object creation
        print("\nTesting RunCard object creation:")
        test_path = "./test_temp"
        runcard = RC.Runcard(
            test_path=test_path,
            test_case="TEST-0000",
            script_version="0.0.1"
        )
        print(f"  ✓ RunCard object created successfully")
        print(f"  - test_path: {runcard.path}")
        print(f"  - test_case: {runcard.test_case}")
        print(f"  - script_version: {runcard.script_version}")
        print(f"  - test_result: {runcard.test_result}")
        
        # Test enum values
        print("\nTesting enum values:")
        print(f"  - TestResult.PASS: {RC.TestResult.PASS.value}")
        print(f"  - TestResult.FAIL: {RC.TestResult.FAIL.value}")
        print(f"  - TestResult.ONGOING: {RC.TestResult.ONGOING.value}")
        
        print("\n" + "=" * 60)
        print("✓ All checks passed! RunCard is usable")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"✗ ImportError: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ Runtime error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_runcard_import()
    sys.exit(0 if success else 1)
