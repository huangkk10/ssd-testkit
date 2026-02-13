"""
Build Script for PyInstaller Packaging

Reads build_config.yaml and generates PyInstaller executable.
Automates the packaging process with sensible defaults.
"""

import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Please run: pip install pyyaml")
    sys.exit(1)


class BuildConfig:
    """Build configuration manager."""
    
    DEFAULT_CONFIG = {
        'version': '1.0.0',
        'project_name': 'RunTest',
        'test_projects': [],
        'build': {
            'mode': 'onedir',
            'console': True,
            'icon': None,
        },
        'release': {
            'create_zip': True,
            'create_readme': True,
        }
    }
    
    def __init__(self, config_file: Path):
        """Load configuration from YAML file."""
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load and merge configuration with defaults."""
        if not self.config_file.exists():
            print(f"WARNING: Config file not found: {self.config_file}")
            print("Using default configuration")
            return self.DEFAULT_CONFIG.copy()
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
        
        # Merge with defaults
        config = self.DEFAULT_CONFIG.copy()
        config.update(user_config)
        
        # Merge nested dicts
        if 'build' in user_config:
            config['build'].update(user_config['build'])
        if 'release' in user_config:
            config['release'].update(user_config['release'])
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def display(self):
        """Display current configuration."""
        print("\n" + "=" * 70)
        print("BUILD CONFIGURATION")
        print("=" * 70)
        print(yaml.dump(self.config, default_flow_style=False, allow_unicode=True))
        print("=" * 70)


class PyInstallerBuilder:
    """PyInstaller build manager."""
    
    def __init__(self, config: BuildConfig, packaging_dir: Path):
        """Initialize builder."""
        self.config = config
        self.packaging_dir = packaging_dir
        self.project_root = packaging_dir.parent
        self.dist_dir = packaging_dir / 'dist'
        self.build_dir = packaging_dir / 'build'
        self.spec_file = packaging_dir / 'run_test.spec'
    
    def clean(self):
        """Clean build artifacts."""
        print("\n" + "=" * 70)
        print("CLEANING BUILD ARTIFACTS")
        print("=" * 70)
        
        dirs_to_clean = [self.dist_dir, self.build_dir]
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                print(f"Removing: {dir_path}")
                shutil.rmtree(dir_path)
        
        print("Clean complete")
    
    def check_dependencies(self) -> bool:
        """Check if PyInstaller is installed."""
        try:
            import PyInstaller
            print(f"[OK] PyInstaller {PyInstaller.__version__} found")
            return True
        except ImportError:
            print("[ERROR] PyInstaller not found")
            print("\nPlease install PyInstaller:")
            print("  pip install pyinstaller")
            return False
    
    def generate_spec_file(self) -> bool:
        """Generate run_test.spec file if it doesn't exist."""
        if self.spec_file.exists():
            print(f"[OK] Spec file exists: {self.spec_file}")
            return True
        
        print(f"Generating spec file: {self.spec_file}")
        
        # Read requirements.txt for hidden imports
        requirements_file = self.project_root / 'requirements.txt'
        hidden_imports = []
        
        # Map package names to actual module names
        package_to_module = {
            'pytest-order': 'pytest_order',
            'pytest-asyncio': 'pytest_asyncio',
            'pywin32': None,  # pywin32 is handled by PyInstaller hooks
            'Pillow': 'PIL',
            'async-timeout': 'async_timeout',
            'WMI': 'wmi',
        }
        
        if requirements_file.exists():
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        pkg = line.split('>=')[0].split('==')[0].split('<')[0].strip()
                        # Convert package name to module name
                        module = package_to_module.get(pkg, pkg)
                        if module:  # Skip None values
                            hidden_imports.append(module)
        
        # Get test projects from config
        test_projects = self.config.get('test_projects', [])
        
        # Build datas list
        datas_lines = []
        
        # Add test projects (with exclude patterns for venv, cache, etc.)
        for test_project in test_projects:
            # We'll use Tree in spec to have better control over excludes
            pass
        
        # Add support files (only internal dependencies)
        datas_lines.extend([
            "    ('../tests/__init__.py', 'tests'),",
            "    ('../tests/integration/__init__.py', 'tests/integration'),",
            "    ('../tests/integration/Config', 'tests/integration/Config'),",
            "    ('../tests/integration/lib', 'tests/integration/lib'),",
            "    ('../framework', 'framework'),",
            "    ('../lib', 'lib'),",
            "    ('../pytest.ini', '.'),",
            "    ('build_config.yaml', '.'),",  # Include config file for default test project
        ])
        
        datas_str = '\n'.join(datas_lines)
        
        # Build Tree entries for test projects with excludes
        test_trees = []
        for test_project in test_projects:
            test_trees.append(f"    Tree('../{test_project}', prefix='{test_project}', excludes=['**/*_venv', '**/*_venv/**', '**/__pycache__', '**/*.pyc', '**/*.pyo', '**/.git', '**/.pytest_cache', '**/venv', '**/venv/**', '**/.venv', '**/.venv/**']),")
        test_trees_str = '\n'.join(test_trees)
        
        # Build hiddenimports list
        hidden_imports_str = ',\n        '.join(f"'{pkg}'" for pkg in hidden_imports)
        
        # Check if bin directory exists
        bin_dir = self.project_root / 'bin'
        bin_exists = bin_dir.exists()
        
        # Build COLLECT data sources (do not include test trees - will be copied in post-process)
        collect_sources = [
            "exe,",
            "a.binaries,",
            "a.zipfiles,",
            "a.datas,"
        ]
        if bin_exists:
            collect_sources.append("Tree('../bin', prefix='bin'),")
        
        collect_sources_str = '\n    '.join(collect_sources)
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for SSD-TestKit
# Auto-generated by build.py

block_cipher = None

a = Analysis(
    ['run_test.py'],
    pathex=[],
    binaries=[],
    datas=[
{datas_str}
    ],
    hiddenimports=[
        {hidden_imports_str}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{self.config.get("project_name", "RunTest")}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console={self.config.get('build', {}).get('console', True)},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
        
        with open(self.spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        print(f"[OK] Generated spec file: {self.spec_file}")
        return True
    
    def run_pyinstaller(self) -> bool:
        """Run PyInstaller to build executable."""
        print("\n" + "=" * 70)
        print("RUNNING PYINSTALLER")
        print("=" * 70)
        
        cmd = [
            'pyinstaller',
            '--clean',
            '--noconfirm',
            str(self.spec_file),
        ]
        
        print(f"Command: {' '.join(cmd)}")
        print()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.packaging_dir),
                check=True,
            )
            
            print("\n[OK] PyInstaller build completed")
            
            # Post-process: copy bin and Config to dist root
            self._post_process_dist()
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] PyInstaller build failed with exit code {e.returncode}")
            return False
        except Exception as e:
            print(f"\n[ERROR] Build error: {e}")
            return False
    
    def _post_process_dist(self):
        """Post-process dist directory: copy bin and Config from test project to dist subfolder."""
        import shutil
        import os
        
        project_name = self.config.get('project_name', 'RunTest')
        dist_dir = self.packaging_dir / 'dist'
        exe_file = dist_dir / f'{project_name}.exe'
        
        # Check if exe was created
        if not exe_file.exists():
            print(f"[WARNING] Executable not found at {exe_file}")
            return
        
        print("\nPost-processing dist directory...")
        
        # Get first test project (assuming single test project for now)
        test_projects = self.config.get('test_projects', [])
        if not test_projects:
            print("[WARNING] No test projects configured")
            return
        
        # Get output folder name from config or extract from test project path
        output_folder_name = self.config.get('output_folder_name', '')
        if not output_folder_name:
            # Fallback: extract subfolder name from test project path (last segment)
            test_project_rel = test_projects[0]
            output_folder_name = Path(test_project_rel).name
        
        # Combine with version
        version = self.config.get('version', '1.0.0')
        subfolder_name = f"{output_folder_name}_v{version}"
        
        # Create subfolder in dist
        target_dist_dir = dist_dir / subfolder_name
        target_dist_dir.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created target directory: dist/{subfolder_name}")
        
        # Move exe to subfolder
        target_exe_file = target_dist_dir / f'{project_name}.exe'
        if exe_file.exists() and exe_file != target_exe_file:
            shutil.move(str(exe_file), str(target_exe_file))
            print(f"[OK] Moved {project_name}.exe to dist/{subfolder_name}/")
        
        test_project_path = self.project_root / self.config.get('test_projects', [])[0]
        if not test_project_path.exists():
            print(f"[WARNING] Test project not found: {test_project_path}")
            return
        
        # Copy bin from test project to dist subfolder
        bin_src = test_project_path / 'bin'
        bin_dst = target_dist_dir / 'bin'
        if bin_src.exists():
            if bin_dst.exists():
                shutil.rmtree(bin_dst)
            
            # Copy with exclusions
            def ignore_venv(dir_path, names):
                ignored = []
                for name in names:
                    if 'venv' in name.lower() or name in ['__pycache__', '.pytest_cache']:
                        ignored.append(name)
                    elif name.endswith(('.pyc', '.pyo')):
                        ignored.append(name)
                return ignored
            
            shutil.copytree(bin_src, bin_dst, ignore=ignore_venv)
            print(f"[OK] Copied bin/ to dist/{subfolder_name}/bin")
        
        # Copy Config from test project to dist subfolder
        config_src = test_project_path / 'Config'
        config_dst = target_dist_dir / 'Config'
        if config_src.exists():
            if config_dst.exists():
                shutil.rmtree(config_dst)
            shutil.copytree(config_src, config_dst)
            print(f"[OK] Copied Config/ to dist/{subfolder_name}/Config")
        
        # Copy convenience batch files if they exist
        bat_files = [
            'run_tests.bat',
            'run_single_test.bat',
            'quick_test.bat',
            'view_logs.bat'
        ]
        for bat_file in bat_files:
            bat_src = self.packaging_dir / bat_file
            if not bat_src.exists():
                # Create default batch file
                bat_src = dist_dir / bat_file
            if bat_src.exists():
                bat_dst = target_dist_dir / bat_file
                if bat_dst.exists():
                    bat_dst.unlink()
                if bat_src != bat_dst:
                    shutil.copy2(bat_src, bat_dst)
                print(f"[OK] Copied {bat_file} to dist/{subfolder_name}/")
        
        # Copy test files to dist subfolder (maintaining relative path structure)
        # e.g., tests/integration/.../stc1685_burnin -> dist/stc1685_burnin/tests/integration/.../stc1685_burnin
        test_src = test_project_path  # Full path to test directory
        # Extract relative path from project root
        test_rel_path = test_project_path.relative_to(self.project_root)
        test_dst = target_dist_dir / test_rel_path
        
        if test_src.exists():
            # Remove destination if it exists
            if test_dst.exists():
                shutil.rmtree(test_dst)
            
            # Copy test directory with exclusions
            def ignore_test_files(dir_path, names):
                ignored = []
                for name in names:
                    # Skip venv, cache, bin, Config (already copied to root), log directories
                    if any(x in name.lower() for x in ['venv', '__pycache__', '.pytest_cache']):
                        ignored.append(name)
                    elif name in ['bin', 'Config', 'log', 'testlog']:
                        ignored.append(name)
                    elif name.endswith(('.pyc', '.pyo')):
                        ignored.append(name)
                return ignored
            
            shutil.copytree(test_src, test_dst, ignore=ignore_test_files)
            print(f"[OK] Copied test files to dist/{subfolder_name}/{test_rel_path}")
        
        print(f"\n[OK] Final structure:")
        print(f"  dist/")
        print(f"    └── {subfolder_name}/")
        print(f"        ├── {project_name}.exe")
        if config_dst.exists():
            print(f"        ├── Config/")
            if (config_dst / 'Config.json').exists():
                print(f"        │   └── Config.json")
        if bin_dst.exists():
            print(f"        ├── bin/")
        if test_dst.exists():
            print(f"        └── {test_rel_path}/")
    
    def create_release(self):
        """Create release package."""
        if not self.config.get('release', {}).get('create_zip', True):
            return
        
        print("\n" + "=" * 70)
        print("CREATING RELEASE PACKAGE")
        print("=" * 70)
        
        # Find the built executable directory
        exe_name = self.config.get('project_name', 'RunTest')
        exe_dir = self.dist_dir / exe_name
        
        if not exe_dir.exists():
            print(f"[ERROR] Executable directory not found: {exe_dir}")
            return
        
        # Create release directory
        release_dir = self.packaging_dir / 'release'
        release_dir.mkdir(parents=True, exist_ok=True)
        
        # Create ZIP
        version = self.config.get('version', '1.0.0')
        zip_name = f"{exe_name}_v{version}"
        zip_path = release_dir / zip_name
        
        print(f"Creating ZIP: {zip_path}.zip")
        shutil.make_archive(str(zip_path), 'zip', self.dist_dir, exe_name)
        
        print(f"[OK] Release package created: {zip_path}.zip")
        print(f"  Size: {(zip_path.with_suffix('.zip').stat().st_size / 1024 / 1024):.1f} MB")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Build SSD-TestKit executable with PyInstaller'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='build_config.yaml',
        help='Build configuration file (default: build_config.yaml)'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean build artifacts before building'
    )
    
    parser.add_argument(
        '--show-config',
        action='store_true',
        help='Show configuration and exit'
    )
    
    parser.add_argument(
        '--spec-only',
        action='store_true',
        help='Generate spec file only, do not build'
    )
    
    parser.add_argument(
        '--no-release',
        action='store_true',
        help='Skip release package creation'
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    print("=" * 70)
    print("SSD-TestKit PyInstaller Build Script")
    print("=" * 70)
    
    args = parse_args()
    
    # Get paths
    packaging_dir = Path(__file__).parent
    config_file = packaging_dir / args.config
    
    # Load configuration
    print(f"\nLoading configuration from: {config_file}")
    config = BuildConfig(config_file)
    
    if args.show_config:
        config.display()
        return 0
    
    # Create builder
    builder = PyInstallerBuilder(config, packaging_dir)
    
    # Clean if requested
    if args.clean:
        builder.clean()
    
    # Check dependencies
    print("\nChecking dependencies...")
    if not builder.check_dependencies():
        return 1
    
    # Generate spec file
    print("\nGenerating spec file...")
    if not builder.generate_spec_file():
        return 1
    
    if args.spec_only:
        print(f"\n[OK] Spec file generated (--spec-only mode)")
        return 0
    
    # Run PyInstaller
    if not builder.run_pyinstaller():
        return 1
    
    # Create release package
    if not args.no_release:
        builder.create_release()
    
    # Summary
    print("\n" + "=" * 70)
    print("BUILD SUMMARY")
    print("=" * 70)
    print(f"[OK] Build completed successfully")
    print(f"  Output: {builder.dist_dir / config.get('project_name', 'RunTest')}")
    print(f"  Executable: {config.get('project_name', 'RunTest')}.exe")
    print("=" * 70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
