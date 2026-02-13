#!/usr/bin/env python3
"""检查 PyInstaller 构建状态"""

import os
import sys
from pathlib import Path

def check_build_status():
    """检查构建状态"""
    packaging_dir = Path(__file__).parent
    dist_dir = packaging_dir / 'dist' / 'RunTest_STC1685'
    exe_file = dist_dir / 'RunTest_STC1685.exe'
    
    print("=" * 70)
    print("PyInstaller Build Status Check")
    print("=" * 70)
    print()
    
    # Check dist directory
    if dist_dir.exists():
        print(f"[OK] Dist directory exists: {dist_dir}")
        
        # List files
        files = list(dist_dir.glob('*'))
        print(f"[OK] Found {len(files)} files/folders in dist")
        
        # Check for executable
        if exe_file.exists():
            size_mb = exe_file.stat().st_size / (1024 * 1024)
            print(f"[OK] Executable found: {exe_file.name} ({size_mb:.1f} MB)")
            print()
            print("=" * 70)
            print("BUILD SUCCESSFUL!")
            print("=" * 70)
            print()
            print("Next steps:")
            print(f"  1. Test paths: {exe_file} --show-paths")
            print(f"  2. Dry run:    {exe_file} --test <test_path> --dry-run")
            print(f"  3. Run test:   {exe_file} --test <test_path>")
            return True
        else:
            print("[WAIT] Executable not found yet - build may still be running")
            print()
            print("Expected location:")
            print(f"  {exe_file}")
            return False
    else:
        print("[WAIT] Dist directory not found - build has not started or failed")
        print()
        print("Expected location:")
        print(f"  {dist_dir}")
        return False

if __name__ == '__main__':
    success = check_build_status()
    sys.exit(0 if success else 1)
