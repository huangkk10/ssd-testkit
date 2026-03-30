#!/usr/bin/env python3
"""Check PyInstaller build status by reading build_config.yaml dynamically."""

import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Please run: pip install pyyaml")
    sys.exit(1)


def _get_release_name(config: dict) -> str:
    """Derive the dist subfolder name from build_config.yaml (mirrors build.py logic)."""
    release_name = config.get('release_name', '').strip()
    if release_name:
        return release_name.replace('{date}', date.today().strftime('%Y%m%d'))

    output_folder_name = config.get('output_folder_name', '')
    if not output_folder_name:
        test_projects = config.get('test_projects', [])
        output_folder_name = Path(test_projects[0]).name if test_projects else 'RunTest'
    version = config.get('version', '1.0.0')
    return f"{output_folder_name}_v{version}"


def check_build_status():
    """Check build status based on current build_config.yaml."""
    packaging_dir = Path(__file__).parent
    config_file = packaging_dir / 'build_config.yaml'

    print("=" * 70)
    print("PyInstaller Build Status Check")
    print("=" * 70)

    # Load config
    if not config_file.exists():
        print(f"[ERROR] build_config.yaml not found: {config_file}")
        return False

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    project_name = config.get('project_name', 'RunTest')
    subfolder_name = _get_release_name(config)
    test_projects = config.get('test_projects', [])

    print(f"  project_name : {project_name}")
    print(f"  release_name : {subfolder_name}")
    print(f"  test_projects: {test_projects}")
    print()

    dist_dir = packaging_dir / 'dist' / subfolder_name
    exe_file = dist_dir / f'{project_name}.exe'

    # Check dist subfolder
    if not dist_dir.exists():
        print(f"[WAIT] Dist folder not found: {dist_dir}")
        print("       Build has not been run or failed.")
        return False

    print(f"[OK] Dist folder: {dist_dir}")
    items = list(dist_dir.glob('*'))
    print(f"[OK] Contents ({len(items)} items):")
    for item in sorted(items):
        tag = "/" if item.is_dir() else ""
        print(f"       {item.name}{tag}")

    print()

    # Check executable
    if not exe_file.exists():
        print(f"[FAIL] Executable not found: {exe_file.name}")
        return False

    size_mb = exe_file.stat().st_size / (1024 * 1024)
    print(f"[OK] Executable: {exe_file.name}  ({size_mb:.1f} MB)")

    # Check Config/
    config_dst = dist_dir / 'Config'
    if config_dst.exists():
        cfg_files = list(config_dst.iterdir())
        print(f"[OK] Config/  ({len(cfg_files)} file(s))")
    else:
        print("[WARN] Config/ not found in dist")

    # Check bin/
    bin_dst = dist_dir / 'bin'
    if bin_dst.exists():
        bin_items = list(bin_dst.iterdir())
        print(f"[OK] bin/  ({len(bin_items)} item(s))")
    else:
        print("[WARN] bin/ not found in dist")

    # Check test files for each test project
    project_root = packaging_dir.parent
    for tp in test_projects:
        tp_rel = Path(tp)
        tp_dst = dist_dir / tp_rel
        if tp_dst.exists():
            print(f"[OK] {tp}/")
        else:
            print(f"[WARN] {tp}/ not found in dist")

    # Check release ZIP
    release_dir = packaging_dir / 'release'
    zip_file = release_dir / f'{subfolder_name}.zip'
    if zip_file.exists():
        zip_mb = zip_file.stat().st_size / (1024 * 1024)
        print(f"[OK] Release ZIP: {zip_file.name}  ({zip_mb:.1f} MB)")
    else:
        print(f"[INFO] Release ZIP not found: {zip_file.name}")

    print()
    print("=" * 70)
    print("BUILD SUCCESSFUL!")
    print("=" * 70)
    print()
    print("Usage:")
    print(f"  {exe_file} --show-paths")
    print(f"  {exe_file} --test <test_path> --dry-run")
    print(f"  {exe_file} --test <test_path>")
    return True


if __name__ == '__main__':
    success = check_build_status()
    sys.exit(0 if success else 1)
