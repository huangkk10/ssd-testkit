"""
Build Script for PyInstaller Packaging

Reads build_config.yaml and generates PyInstaller executable.
Automates the packaging process with sensible defaults.
"""

import sys
import os
import shutil
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
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
        
        # Prepend stdlib modules that PyInstaller 6.x may miss
        stdlib_hidden = [
            'linecache',
            'tokenize',
            'token',
            'dis',
            'opcode',
        ]
        # pywin32 C extension DLLs are not auto-detected by PyInstaller;
        # pywinauto and wmi depend on many of these.
        pywin32_hidden = [
            'win32api',
            'win32con',
            'win32gui',
            'win32process',
            'win32security',
            'win32service',
            'win32event',
            'win32file',
            'win32pipe',
            'win32print',
            'win32clipboard',
            'win32ts',
            'winerror',
            'pywintypes',
            'pythoncom',
            'win32com',
            'win32com.client',
            'win32com.server',
            'win32com.shell',
            'win32com.shell.shell',
            'win32com.shell.shellcon',
        ]
        all_hidden_imports = stdlib_hidden + pywin32_hidden + hidden_imports
        hidden_imports_str = ',\n        '.join(f"'{pkg}'" for pkg in all_hidden_imports)

        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for SSD-TestKit
# Auto-generated by build.py

block_cipher = None

a = Analysis(
    ['run_test.py'],
    pathex=['..'],  # Ensure ssd-testkit root is found before PYTHONPATH entries
    binaries=[],
    datas=[
{datas_str}
    ],
    hiddenimports=[
        # stdlib modules not always auto-detected by PyInstaller 6.x
        # third-party dependencies
        {hidden_imports_str}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=['run_test_hook.py'],
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
            # Remove PYTHONPATH from subprocess env so PyInstaller analysis
            # does not pick up external paths (e.g. C:\automation) and bundle
            # wrong versions of framework/, lib/, etc.
            build_env = os.environ.copy()
            build_env.pop('PYTHONPATH', None)

            result = subprocess.run(
                cmd,
                cwd=str(self.packaging_dir),
                env=build_env,
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
    
    def _get_release_name(self) -> str:
        """
        Return the dist subfolder / ZIP base name.

        Priority:
          1. ``release_name`` in build_config.yaml (if non-empty)
             - ``{date}`` is replaced with today's date in YYYYMMDD format.
          2. Fallback: ``{output_folder_name}_v{version}``
        """
        from datetime import date as _date

        release_name = self.config.get('release_name', '').strip()
        if release_name:
            today = _date.today().strftime('%Y%m%d')
            return release_name.replace('{date}', today)

        # Default: stc1685_burnin_v1.0.0
        output_folder_name = self.config.get('output_folder_name', '')
        if not output_folder_name:
            test_projects = self.config.get('test_projects', [])
            output_folder_name = Path(test_projects[0]).name if test_projects else 'RunTest'
        version = self.config.get('version', '1.0.0')
        return f"{output_folder_name}_v{version}"

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
        
        subfolder_name = self._get_release_name()
        target_dist_dir = dist_dir / subfolder_name

        # Wipe the entire target dist subfolder so every build starts clean.
        # This prevents stale files from previous builds accumulating.
        if target_dist_dir.exists():
            print(f"Removing old dist folder: {target_dist_dir}")

            def _force_remove_all(func, path, exc_info):
                import stat as _stat
                try:
                    os.chmod(path, _stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass

            shutil.rmtree(target_dist_dir, onerror=_force_remove_all)
            # Fallback via cmd for any kernel-locked files (e.g. .sys drivers)
            if target_dist_dir.exists():
                import subprocess as _sp
                _sp.run(['cmd', '/c', 'rmdir', '/S', '/Q', str(target_dist_dir)],
                        check=False)

        # (Re)create the now-empty target directory
        target_dist_dir.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created target directory: dist/{subfolder_name}")
        
        # Move exe to subfolder
        target_exe_file = target_dist_dir / f'{project_name}.exe'
        if exe_file.exists() and exe_file != target_exe_file:
            if target_exe_file.exists():
                try:
                    target_exe_file.unlink()
                except PermissionError:
                    import subprocess as _spd
                    _spd.run(['cmd', '/c', 'del', '/F', '/Q', str(target_exe_file)], check=False)
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
                def _force_remove(func, path, exc_info):
                    import stat as _stat, os as _os
                    try:
                        _os.chmod(path, _stat.S_IWRITE)
                        func(path)
                    except Exception:
                        pass
                shutil.rmtree(bin_dst, onerror=_force_remove)
                # Fallback: force-remove via cmd if any locked file remains
                if bin_dst.exists():
                    import subprocess as _sp
                    _sp.run(['cmd', '/c', 'rmdir', '/S', '/Q', str(bin_dst)],
                            check=False)

            # Copy with exclusions
            def ignore_venv(dir_path, names):
                ignored = []
                blocked_dirs = {'__pycache__', '.pytest_cache', 'venv', '.venv',
                                'smiwintool_venv'}
                for name in names:
                    full_path = Path(dir_path) / name
                    if full_path.is_dir() and name.lower() in blocked_dirs:
                        ignored.append(name)
                    elif name.endswith(('.pyc', '.pyo')):
                        ignored.append(name)
                return ignored

            # Custom copy: if a file is locked by the Windows kernel (e.g.
            # WinIoEx.sys loaded as a driver service), stop+delete the driver
            # service to release the lock, then retry the copy.
            def _safe_copy2(src, dst):
                try:
                    shutil.copy2(src, dst)
                except PermissionError:
                    fname = os.path.basename(src)
                    if fname.lower().endswith('.sys'):
                        print(f"  [INFO] {fname} is locked. Attempting to unload driver...")
                        if self._unload_kernel_driver(src):
                            # Short pause to let Windows release the handle
                            import time
                            time.sleep(1)
                            try:
                                shutil.copy2(src, dst)
                                print(f"  [OK] {fname} copied after driver unload")
                                return
                            except PermissionError:
                                pass
                        # Unload failed or retry still denied – keep existing copy
                        if os.path.exists(dst):
                            print(f"  [SKIP] {fname} still locked after unload attempt. "
                                  f"Existing copy kept. Reboot if you need to update it.")
                            return
                    raise

            shutil.copytree(bin_src, bin_dst, ignore=ignore_venv,
                            copy_function=_safe_copy2, dirs_exist_ok=True)
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

            # Walk up from test_src to project_root, copying __init__.py and
            # conftest.py for each ancestor package. Ensures the full package
            # chain has __init__.py so pytest prepend importmode resolves the
            # project root correctly (prevents fallback to external PYTHONPATH).
            parent = test_src.parent
            while True:
                try:
                    rel = parent.relative_to(self.project_root)
                except ValueError:
                    break
                for fname in ('__init__.py', 'conftest.py'):
                    fsrc = parent / fname
                    fdst = target_dist_dir / rel / fname
                    if fsrc.exists() and not fdst.exists():
                        fdst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(fsrc), str(fdst))
                        print(f"[OK] Copied {rel / fname} to dist")
                    elif fname == '__init__.py' and not fdst.exists():
                        # Auto-create empty __init__.py to maintain package chain
                        fdst.parent.mkdir(parents=True, exist_ok=True)
                        fdst.touch()
                        print(f"[OK] Created empty {rel / fname} in dist")
                if parent == self.project_root:
                    break
                parent = parent.parent
        
        # Copy pytest.ini to dist folder so rootdir = dist folder (not _MEIPASS).
        # This prevents pytest from scanning upward past the dist folder and
        # accidentally discovering conftest.py files in parent directories
        # (e.g. C:\automation\conftest.py) which would pollute sys.path.
        pytest_ini_src = self.project_root / 'pytest.ini'
        pytest_ini_dst = target_dist_dir / 'pytest.ini'
        if pytest_ini_src.exists():
            shutil.copy2(str(pytest_ini_src), str(pytest_ini_dst))
            print(f"[OK] Copied pytest.ini to dist/{subfolder_name}/")

        print(f"\n[OK] Final structure:")
        print(f"  dist/")
        print(f"    +-- {subfolder_name}/")
        print(f"        +-- {project_name}.exe")
        if config_dst.exists():
            print(f"        +-- Config/")
            if (config_dst / 'Config.json').exists():
                print(f"        |   +-- Config.json")
        if bin_dst.exists():
            print(f"        +-- bin/")
        if test_dst.exists():
            print(f"        +-- {test_rel_path}/")
    
    def _unload_kernel_driver(self, sys_path: str) -> bool:
        """
        Stop and delete the kernel driver service that is locking a .sys file.

        Searches HKLM\\SYSTEM\\CurrentControlSet\\Services for a service whose
        ImagePath contains the filename, then runs 'sc stop' + 'sc delete'.

        Returns True if the driver was successfully unloaded.
        """
        import winreg
        import subprocess as _sp

        sys_filename = os.path.basename(sys_path).lower()
        service_name = None

        # --- Search registry for the service that owns this .sys file ---
        try:
            svc_key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r'SYSTEM\CurrentControlSet\Services'
            )
            idx = 0
            while True:
                try:
                    name = winreg.EnumKey(svc_key, idx)
                    sub = winreg.OpenKey(svc_key, name)
                    try:
                        img, _ = winreg.QueryValueEx(sub, 'ImagePath')
                        if sys_filename in img.lower():
                            service_name = name
                    except FileNotFoundError:
                        pass
                    finally:
                        winreg.CloseKey(sub)
                    if service_name:
                        break
                    idx += 1
                except OSError:
                    break
            winreg.CloseKey(svc_key)
        except Exception as e:
            print(f"  [WARNING] Registry search failed: {e}")
            return False

        if not service_name:
            print(f"  [WARNING] No driver service found for {sys_filename}")
            return False

        print(f"  [INFO] Found kernel driver service: {service_name}")

        # --- Stop the service ---
        r = _sp.run(['sc', 'stop', service_name],
                    capture_output=True, text=True)
        # 1062 = ERROR_SERVICE_NOT_ACTIVE (already stopped)
        if r.returncode not in (0, 1062):
            print(f"  [WARNING] sc stop {service_name} failed: {r.stdout.strip()}")

        # --- Delete (unregister) the service so Windows releases the file ---
        r = _sp.run(['sc', 'delete', service_name],
                    capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [WARNING] sc delete {service_name} failed: {r.stdout.strip()}")
            return False

        print(f"  [OK] Kernel driver service '{service_name}' stopped and deleted")
        return True

    def create_release(self):
        """Create release package (zips assembled dist subfolder)."""
        if not self.config.get('release', {}).get('create_zip', True):
            return

        print("\n" + "=" * 70)
        print("CREATING RELEASE PACKAGE")
        print("=" * 70)

        subfolder_name = self._get_release_name()
        subfolder_dir = self.dist_dir / subfolder_name

        if not subfolder_dir.exists():
            print(f"[ERROR] Dist subfolder not found: {subfolder_dir}")
            return

        release_dir = self.packaging_dir / 'release'
        release_dir.mkdir(parents=True, exist_ok=True)

        zip_path = release_dir / subfolder_name
        print(f"Creating ZIP: {zip_path}.zip")

        # Temporarily restore original stdout/stderr during make_archive.
        # The _Tee wrapper's fileno() delegation can cause zipfile's internal
        # file-I/O to truncate the ZIP if it flushes through the wrong fd.
        _tee_stdout = sys.stdout
        _tee_stderr = sys.stderr
        _orig = getattr(_tee_stdout, '_streams', None)
        if _orig:
            sys.stdout = _orig[0]
            sys.stderr = getattr(_tee_stderr, '_streams', [_tee_stderr])[0]
        try:
            shutil.make_archive(str(zip_path), 'zip', str(self.dist_dir), subfolder_name)
        finally:
            sys.stdout = _tee_stdout
            sys.stderr = _tee_stderr

        size_mb = Path(str(zip_path) + '.zip').stat().st_size / 1024 / 1024
        print(f"[OK] Release package created: {zip_path}.zip")
        print(f"  Size: {size_mb:.1f} MB")


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
    # Tee all stdout/stderr to build_output.log in the packaging directory
    # so every build automatically produces a log file alongside console output.
    import io

    class _Tee:
        def __init__(self, *streams):
            self._streams = streams
        def write(self, data):
            for s in self._streams:
                try:
                    s.write(data)
                except Exception:
                    pass
        def flush(self):
            for s in self._streams:
                try:
                    s.flush()
                except Exception:
                    pass
        def fileno(self):
            return self._streams[0].fileno()

    log_path = Path(__file__).parent / 'build_output.log'
    _log_file = open(log_path, 'w', encoding='utf-8', errors='replace')
    _orig_stdout = sys.stdout
    _orig_stderr = sys.stderr
    sys.stdout = _Tee(_orig_stdout, _log_file)
    sys.stderr = _Tee(_orig_stderr, _log_file)

    try:
        return _main_impl()
    finally:
        sys.stdout = _orig_stdout
        sys.stderr = _orig_stderr
        _log_file.close()


def _main_impl() -> int:
    """Actual build logic (called by main after Tee is set up)."""
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
