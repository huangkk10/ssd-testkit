"""
SmiCli Path Verification Script
Verify availability of SmiCli2.exe at expected locations
"""
from pathlib import Path

def verify_smicli_paths():
    """Verify SmiCli paths"""
    print("=" * 60)
    print("SmiCli2.exe path verification")
    print("=" * 60)
    
    # Get test directory (from tests/verification/ back to project root)
    project_root = Path(__file__).resolve().parents[2]
    test_dir = project_root / "tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin"
    
    # Define paths to check (in priority order)
    smicli_paths = [
        {
            'priority': 1,
            'name': 'test directory',
            'path': test_dir / "bin/SmiWinTools/bin/x64/SmiCli2.exe"
        },
        {
            'priority': 2,
            'name': 'project root',
            'path': project_root / "bin/SmiWinTools/bin/x64/SmiCli2.exe"
        },
        {
            'priority': 3,
            'name': 'global (legacy) path',
            'path': Path("C:/automation/bin/SmiCli/SmiCli2.exe")
        },
    ]
    
    found_paths = []
    
    print("\nPath check results:")
    print("-" * 60)
    
    for item in smicli_paths:
        priority = item['priority']
        name = item['name']
        path = item['path']
        
        exists = path.exists()
        status = "✓ Present" if exists else "✗ Missing"
        
        print(f"[Priority {priority}] {name}")
        print(f"  Path: {path}")
        print(f"  Status: {status}")
        
        if exists:
            found_paths.append(path)
            # Check file size
            size_kb = path.stat().st_size / 1024
            print(f"  Size: {size_kb:.2f} KB")
        
        print()
    
    # 总结
    print("=" * 60)
    if found_paths:
        print(f"✓ Found {len(found_paths)} available SmiCli2.exe")
        print(f"\nRecommended: {found_paths[0]}")
        print("=" * 60)
        return True
    else:
        print("✗ No available SmiCli2.exe found")
        print("  Ensure at least one SmiCli2.exe is present")
        print("=" * 60)
        return False

if __name__ == "__main__":
    import sys
    success = verify_smicli_paths()
    sys.exit(0 if success else 1)
