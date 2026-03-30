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

    def get_test_projects(self, project_root: Path) -> List[str]:
        """
        Return the list of test project paths to package.

        Priority:
          1. Explicit ``test_projects`` list in build_config.yaml (backward compat).
          2. Auto-discover every subdirectory under ``test_root`` that contains
             a ``test_main.py`` file.
        """
        explicit = self.config.get('test_projects', [])
        if explicit:
            return explicit

        test_root = self.config.get('test_root', '').strip()
        if not test_root:
            return []

        root_path = project_root / test_root
        if not root_path.exists():
            return []

        discovered = []
        for d in sorted(root_path.iterdir()):
            if d.is_dir() and not d.name.startswith(('_', '.')):
                if (d / 'test_main.py').exists():
                    discovered.append(f"{test_root}/{d.name}")
        return discovered

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
        test_projects = self.config.get_test_projects(self.project_root)

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

        # Default: use output_folder_name, or test_root leaf, or first test project leaf
        output_folder_name = self.config.get('output_folder_name', '').strip()
        if not output_folder_name:
            test_root = self.config.get('test_root', '').strip()
            if test_root:
                output_folder_name = Path(test_root).name
            else:
                test_projects = self.config.get_test_projects(self.project_root)
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

        test_projects = self.config.get_test_projects(self.project_root)
        if not test_projects:
            print("[WARNING] No test projects configured")
            return

        subfolder_name = self._get_release_name()
        target_dist_dir = dist_dir / subfolder_name

        # Wipe the entire target dist subfolder so every build starts clean.
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
            if target_dist_dir.exists():
                import subprocess as _sp
                _sp.run(['cmd', '/c', 'rmdir', '/S', '/Q', str(target_dist_dir)], check=False)

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

        # ── Shared helpers ────────────────────────────────────────────────────
        def ignore_venv(dir_path, names):
            ignored = []
            blocked_dirs = {'__pycache__', '.pytest_cache', 'venv', '.venv', 'smiwintool_venv'}
            for name in names:
                full_path = Path(dir_path) / name
                if full_path.is_dir() and name.lower() in blocked_dirs:
                    ignored.append(name)
                elif name.endswith(('.pyc', '.pyo')):
                    ignored.append(name)
            return ignored

        def _safe_copy2(src, dst):
            try:
                shutil.copy2(src, dst)
            except PermissionError:
                fname = os.path.basename(src)
                if fname.lower().endswith('.sys'):
                    print(f"  [INFO] {fname} is locked. Attempting to unload driver...")
                    if self._unload_kernel_driver(src):
                        import time
                        time.sleep(1)
                        try:
                            shutil.copy2(src, dst)
                            print(f"  [OK] {fname} copied after driver unload")
                            return
                        except PermissionError:
                            pass
                    if os.path.exists(dst):
                        print(f"  [SKIP] {fname} still locked. Existing copy kept.")
                        return
                raise

        def ignore_test_files(dir_path, names):
            ignored = []
            for name in names:
                if any(x in name.lower() for x in ['venv', '__pycache__', '.pytest_cache']):
                    ignored.append(name)
                elif name in ['bin', 'Config', 'log', 'testlog']:
                    ignored.append(name)
                elif name.endswith(('.pyc', '.pyo')):
                    ignored.append(name)
            return ignored

        # ── Copy bin/ ─────────────────────────────────────────────────────────
        # Source priority:
        #   1. Project-root bin/  (ssd-testkit/bin/)  — main tool repository
        #   2. Each testcase's own bin/ (if present)  — merged on top
        bin_dst = target_dist_dir / 'bin'

        bin_sources = []
        project_bin = self.project_root / 'bin'
        if project_bin.exists():
            bin_sources.append(('bin/ (project root)', project_bin))
        for tp in test_projects:
            tp_bin = self.project_root / tp / 'bin'
            if tp_bin.exists():
                bin_sources.append((f'{tp}/bin/', tp_bin))

        first = True
        for label, bin_src in bin_sources:
            if first and bin_dst.exists():
                def _force_remove(func, path, exc_info):
                    import stat as _stat, os as _os
                    try:
                        _os.chmod(path, _stat.S_IWRITE)
                        func(path)
                    except Exception:
                        pass
                shutil.rmtree(bin_dst, onerror=_force_remove)
                if bin_dst.exists():
                    import subprocess as _sp
                    _sp.run(['cmd', '/c', 'rmdir', '/S', '/Q', str(bin_dst)], check=False)
            shutil.copytree(bin_src, bin_dst, ignore=ignore_venv,
                            copy_function=_safe_copy2, dirs_exist_ok=True)
            print(f"[OK] Merged {label} → dist/{subfolder_name}/bin")
            first = False

        # ── Copy test files — loop over every test project ───────────────────
        for tp in test_projects:
            tp_path = self.project_root / tp
            if not tp_path.exists():
                print(f"[WARNING] Test project not found: {tp}")
                continue

            # Config stays inside testcase dir (Path(__file__).parent / "Config" still works)
            config_src = tp_path / 'Config'
            if config_src.exists():
                tp_rel = tp_path.relative_to(self.project_root)
                config_dst_tp = target_dist_dir / tp_rel / 'Config'
                if config_dst_tp.exists():
                    shutil.rmtree(config_dst_tp)
                shutil.copytree(config_src, config_dst_tp)
                print(f"[OK] Copied {tp}/Config/ → dist/{subfolder_name}/{tp_rel}/Config")

            # Test source files
            test_rel_path = tp_path.relative_to(self.project_root)
            test_dst = target_dist_dir / test_rel_path
            if test_dst.exists():
                shutil.rmtree(test_dst)
            shutil.copytree(tp_path, test_dst, ignore=ignore_test_files)
            print(f"[OK] Copied test files → dist/{subfolder_name}/{test_rel_path}")

            # Ensure __init__.py / conftest.py exist at every ancestor package level
            parent = tp_path.parent
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
                        fdst.parent.mkdir(parents=True, exist_ok=True)
                        fdst.touch()
                        print(f"[OK] Created empty {rel / fname} in dist")
                if parent == self.project_root:
                    break
                parent = parent.parent

        # ── Convenience batch files ───────────────────────────────────────────
        for bat_file in ('run_tests.bat', 'run_single_test.bat', 'quick_test.bat', 'view_logs.bat'):
            bat_src = self.packaging_dir / bat_file
            if not bat_src.exists():
                bat_src = dist_dir / bat_file
            if bat_src.exists():
                bat_dst = target_dist_dir / bat_file
                if bat_dst.exists():
                    bat_dst.unlink()
                if bat_src != bat_dst:
                    shutil.copy2(bat_src, bat_dst)
                print(f"[OK] Copied {bat_file} to dist/{subfolder_name}/")

        # ── pytest.ini ────────────────────────────────────────────────────────
        pytest_ini_src = self.project_root / 'pytest.ini'
        pytest_ini_dst = target_dist_dir / 'pytest.ini'
        if pytest_ini_src.exists():
            shutil.copy2(str(pytest_ini_src), str(pytest_ini_dst))
            print(f"[OK] Copied pytest.ini to dist/{subfolder_name}/")

        # ── Print final structure ─────────────────────────────────────────────
        print(f"\n[OK] Final structure:")
        print(f"  dist/")
        print(f"    +-- {subfolder_name}/")
        print(f"        +-- {project_name}.exe")
        print(f"        +-- pytest.ini")
        if bin_dst.exists():
            print(f"        +-- bin/")
        print(f"        +-- tests/")
        for tp in test_projects:
            print(f"            +-- {Path(tp).name}/")
    
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


def pre_flight_check(config: 'BuildConfig', project_root: Path) -> bool:
    """
    Pre-flight checks before starting PyInstaller build.

    Validates that all required files and directories exist and
    prints a preview of what will be packaged.

    Returns True if all checks pass, False if any error is found.
    """
    print("\n" + "=" * 70)
    print("PRE-FLIGHT CHECK")
    print("=" * 70)

    errors: list[str] = []
    warnings: list[str] = []

    # ── 1. build_config.yaml 欄位完整性 ──────────────────────────────────
    version = config.get('version', '').strip()
    project_name = config.get('project_name', '').strip()
    test_projects = config.get_test_projects(project_root)

    if not version:
        errors.append("build_config.yaml: 'version' is empty")
    if not project_name:
        errors.append("build_config.yaml: 'project_name' is empty")
    if not test_projects:
        errors.append("build_config.yaml: 'test_projects' is empty — nothing to package")

    print(f"  project_name : {project_name or '(empty)'}")
    print(f"  version      : {version or '(empty)'}")

    release_name = config.get('release_name', '').strip()
    if release_name:
        from datetime import date as _date
        preview_name = release_name.replace('{date}', _date.today().strftime('%Y%m%d'))
        print(f"  release_name : {preview_name}")
    else:
        output_folder_name = config.get('output_folder_name', '') or \
            (Path(test_projects[0]).name if test_projects else 'RunTest')
        print(f"  output_name  : {output_folder_name}_v{version}")

    # ── 2. project-root bin/ ─────────────────────────────────────────────
    project_bin = project_root / 'bin'
    print()
    if project_bin.exists():
        bin_items = list(project_bin.iterdir())
        print(f"  bin/ (project root): {len(bin_items)} item(s)")
        for item in sorted(bin_items):
            tag = "/" if item.is_dir() else ""
            print(f"    [OK]    bin/{item.name}{tag}")
    else:
        print(f"  [WARN]  bin/ (project root)  ← not found")
        warnings.append("bin/ missing at project root")

    # ── 3. test_projects paths and contents ──────────────────────────────
    print(f"\n  test_projects ({len(test_projects)} project(s)):")
    for tp in test_projects:
        tp_path = project_root / tp
        if not tp_path.exists():
            print(f"    [ERROR] {tp}  ← directory not found")
            errors.append(f"test_project not found: {tp}")
            continue

        # Check test_main.py
        main_py = tp_path / 'test_main.py'
        if not main_py.exists():
            print(f"    [ERROR] {tp}/test_main.py  ← not found")
            errors.append(f"test_main.py missing in: {tp}")
        else:
            print(f"    [OK]    {tp}/test_main.py")

        # Check Config/
        config_dir = tp_path / 'Config'
        if not config_dir.exists():
            print(f"    [WARN]  {tp}/Config/  ← not found (Config will be skipped)")
            warnings.append(f"Config/ missing in: {tp}")
        else:
            config_files = list(config_dir.iterdir())
            print(f"    [OK]    {tp}/Config/  ({len(config_files)} file(s))")

    # ── 3. framework / lib ────────────────────────────────────────────────
    print()
    for required_dir in ('framework', 'lib'):
        d = project_root / required_dir
        if not d.exists():
            print(f"  [ERROR] {required_dir}/  ← not found")
            errors.append(f"Required directory missing: {required_dir}")
        else:
            print(f"  [OK]    {required_dir}/")

    # ── 4. pytest.ini ─────────────────────────────────────────────────────
    pytest_ini = project_root / 'pytest.ini'
    if not pytest_ini.exists():
        print(f"  [WARN]  pytest.ini  ← not found")
        warnings.append("pytest.ini missing at project root")
    else:
        print(f"  [OK]    pytest.ini")

    # ── Result ────────────────────────────────────────────────────────────
    print()
    if warnings:
        print(f"  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    [WARN] {w}")

    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for e in errors:
            print(f"    [ERROR] {e}")
        print("\n[FAIL] Pre-flight check failed — fix errors above before building.")
        print("=" * 70)
        return False

    print("[OK] Pre-flight check passed.")
    print("=" * 70)
    return True


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
        '--check',
        action='store_true',
        help='Run pre-flight checks only, do not build'
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

    # Pre-flight check
    if not pre_flight_check(config, builder.project_root):
        return 1

    if args.check:
        return 0

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
