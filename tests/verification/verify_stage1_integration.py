"""
Test Stage 1 Verification
Verify that RunCard integration for stage 1 is correct
"""
import sys
from pathlib import Path

# Add project path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

def verify_integration():
    """Verify RunCard integration"""
    print("=" * 70)
    print("Stage 1: RunCard integration verification")
    print("=" * 70)
    
    test_file = project_root / "tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/test_burnin.py"
    
    print(f"\nReading file: {test_file}")
    
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: RunCard import
    if "from lib.testtool import RunCard as RC" in content:
        checks.append(("✓", "RunCard import present"))
    else:
        checks.append(("✗", "RunCard import missing"))
    
    # Check 2: RunCard initialized in setup_test_class
    if "cls.runcard = RC.Runcard(" in content:
        checks.append(("✓", "RunCard initialized in setup_test_class"))
    else:
        checks.append(("✗", "RunCard initialization missing in setup_test_class"))
    
    # Check 3: start_test call
    if "cls.runcard.start_test(" in content:
        checks.append(("✓", "start_test() call present"))
    else:
        checks.append(("✗", "start_test() call missing"))
    
    # Check 4: end_test call (PASS)
    if "cls.runcard.end_test(RC.TestResult.PASS.value)" in content:
        checks.append(("✓", "end_test() (PASS) call present"))
    else:
        checks.append(("✗", "end_test() (PASS) call missing"))
    
    if "cls.runcard.end_test(RC.TestResult.FAIL.value" in content:
        checks.append(("✓", "end_test() (FAIL) call present"))
    else:
        checks.append(("✗", "end_test() (FAIL) call missing"))
    
    # Check 5: test_passed flag
    if "cls.test_passed = True" in content:
        checks.append(("✓", "test_passed flag initialized"))
    else:
        checks.append(("✗", "test_passed flag missing"))
    
    # Check 6: set flag on failure
    if "self.__class__.test_passed = False" in content:
        checks.append(("✓", "set test_passed flag on failure"))
    else:
        checks.append(("✗", "missing failure flag set"))
    
    # Check 7: RunCard initialization removed from test_05
    test_05_start = content.find("def test_05_burnin_smartcheck(self):")
    test_05_end = content.find("def test_06_cdi_after(self):")
    test_05_content = content[test_05_start:test_05_end]
    
    if "runcard = RC.Runcard(" not in test_05_content:
        checks.append(("✓", "RunCard initialization removed from test_05"))
    else:
        checks.append(("✗", "RunCard initialization still present in test_05"))
    
    # Check 8: SmiCli path
    if "bin/SmiWinTools/bin/x64/SmiCli2.exe" in content:
        checks.append(("✓", "correct SmiCli path used"))
    else:
        checks.append(("✗", "incorrect SmiCli path"))
    
    # Display results
    print("\nVerification results:")
    print("-" * 70)
    for status, message in checks:
        print(f"{status} {message}")
    
    # Summary
    passed = sum(1 for s, _ in checks if s == "✓")
    total = len(checks)
    
    print("\n" + "=" * 70)
    if passed == total:
        print(f"✓ All checks passed! ({passed}/{total})")
        print("=" * 70)
        return True
    else:
        print(f"✗ Some checks failed: {passed}/{total} passed")
        print("=" * 70)
        return False

if __name__ == "__main__":
    success = verify_integration()
    sys.exit(0 if success else 1)
