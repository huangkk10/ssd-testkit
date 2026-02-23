"""
Path Manager for PyInstaller Packaging

Handles path differences between development and packaged environments.
Provides consistent path resolution for both scenarios.
"""

import sys
import os
from pathlib import Path
from typing import Optional


class PathManager:
    """
    Manages paths for both development and packaged (frozen) environments.
    
    In development:
        - BASE_DIR: packaging/ directory
        - APP_DIR: project root directory
    
    In packaged environment:
        - BASE_DIR: _MEIPASS (temporary extraction folder)
        - APP_DIR: directory containing the .exe
    
    Example:
        >>> pm = PathManager()
        >>> config_path = pm.get_config_dir() / 'Config.json'
        >>> bin_path = pm.get_bin_dir() / 'BurnIn' / 'bitwindows.exe'
    """
    
    def __init__(self):
        """Initialize path manager and detect environment."""
        self._is_frozen = getattr(sys, 'frozen', False)
        
        if self._is_frozen:
            # Running in packaged environment
            # _MEIPASS: PyInstaller temporary extraction directory containing bundled files
            self._base_dir = Path(sys._MEIPASS)
            # APP_DIR: directory containing the .exe (the user-visible distribution folder)
            self._app_dir = Path(sys.executable).parent
        else:
            # Running in development environment
            # BASE_DIR: packaging/ directory (directory where this file resides)
            self._base_dir = Path(__file__).parent
            # APP_DIR: project root directory (parent of packaging)
            self._app_dir = self._base_dir.parent
        
        # Configure sys.path for import resolution
        if self._is_frozen:
            # Clear PYTHONPATH env var so pytest cannot re-inject external paths.
            os.environ.pop('PYTHONPATH', None)
            # Restrict sys.path to only _MEIPASS and app_dir.
            _keep = {str(self._base_dir), str(self._app_dir)}
            sys.path = [p for p in sys.path if p in _keep or p == '']
            for _d in (str(self._base_dir), str(self._app_dir)):
                if _d not in sys.path:
                    sys.path.insert(0, _d)
        else:
            # Development: just ensure project root is on sys.path
            project_root = str(self._app_dir)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
    
    @property
    def is_frozen(self) -> bool:
        """Check if running in packaged environment."""
        return self._is_frozen
    
    @property
    def base_dir(self) -> Path:
        """
        Get base directory.
        - Frozen: _MEIPASS (temporary extraction folder)
        - Dev: packaging/ directory
        """
        return self._base_dir
    
    @property
    def app_dir(self) -> Path:
        """
        Get application directory.
        - Frozen: directory containing .exe
        - Dev: project root directory
        """
        return self._app_dir
    
    def get_project_root(self) -> Path:
        """Get project root directory."""
        return self._app_dir
    
    def get_config_dir(self) -> Path:
        """
        Get Config directory path.
        - Frozen: APP_DIR/Config
        - Dev: project_root/Config
        """
        return self._app_dir / 'Config'
    
    def get_bin_dir(self) -> Path:
        """
        Get bin directory path.
        - Frozen: APP_DIR/bin
        - Dev: project_root/bin
        """
        return self._app_dir / 'bin'
    
    def get_log_dir(self) -> Path:
        """
        Get log directory path.
        - Always: APP_DIR/log (created at runtime)
        """
        log_dir = self._app_dir / 'log'
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    
    def get_testlog_dir(self) -> Path:
        """
        Get testlog directory path.
        - Always: APP_DIR/testlog (created at runtime)
        """
        testlog_dir = self._app_dir / 'testlog'
        testlog_dir.mkdir(parents=True, exist_ok=True)
        return testlog_dir
    
    def get_framework_dir(self) -> Path:
        """
        Get framework directory path.
        - Frozen: BASE_DIR/framework (in _MEIPASS)
        - Dev: project_root/framework
        """
        if self._is_frozen:
            return self._base_dir / 'framework'
        return self._app_dir / 'framework'
    
    def get_lib_dir(self) -> Path:
        """
        Get lib directory path.
        - Frozen: BASE_DIR/lib (in _MEIPASS)
        - Dev: project_root/lib
        """
        if self._is_frozen:
            return self._base_dir / 'lib'
        return self._app_dir / 'lib'
    
    def get_tests_dir(self) -> Path:
        """
        Get tests directory path.
        - Frozen: BASE_DIR/tests (in _MEIPASS)
        - Dev: project_root/tests
        """
        if self._is_frozen:
            return self._base_dir / 'tests'
        return self._app_dir / 'tests'
    
    def get_pytest_ini(self) -> Optional[Path]:
        """
        Get pytest.ini path.
        - Frozen: BASE_DIR/pytest.ini (in _MEIPASS)
        - Dev: project_root/pytest.ini
        """
        if self._is_frozen:
            pytest_ini = self._base_dir / 'pytest.ini'
        else:
            pytest_ini = self._app_dir / 'pytest.ini'
        
        return pytest_ini if pytest_ini.exists() else None
    
    def resolve_path(self, relative_path: str) -> Path:
        """
        Resolve a relative path to absolute path.
        
        Args:
            relative_path: Relative path string (e.g., 'Config/Config.json')
        
        Returns:
            Absolute Path object
        
        Example:
            >>> pm = PathManager()
            >>> config = pm.resolve_path('Config/Config.json')
            >>> print(config)
            c:\\automation\\ssd-testkit\\Config\\Config.json
        """
        # If it's already an absolute path, return it directly
        path = Path(relative_path)
        if path.is_absolute():
            return path
        
        # Resolve relative to APP_DIR
        return self._app_dir / relative_path
    
    def get_path_info(self) -> dict:
        """
        Get path information for debugging.
        
        Returns:
            Dictionary with path information
        """
        return {
            'is_frozen': self._is_frozen,
            'base_dir': str(self._base_dir),
            'app_dir': str(self._app_dir),
            'config_dir': str(self.get_config_dir()),
            'bin_dir': str(self.get_bin_dir()),
            'log_dir': str(self.get_log_dir()),
            'testlog_dir': str(self.get_testlog_dir()),
            'framework_dir': str(self.get_framework_dir()),
            'lib_dir': str(self.get_lib_dir()),
            'tests_dir': str(self.get_tests_dir()),
            'pytest_ini': str(self.get_pytest_ini()) if self.get_pytest_ini() else None,
        }
    
    def __repr__(self) -> str:
        """String representation."""
        env = "FROZEN" if self._is_frozen else "DEV"
        return f"PathManager({env}, app_dir={self._app_dir})"


# Create a global instance
path_manager = PathManager()


if __name__ == '__main__':
    # Test the path manager
    print("=== Path Manager Test ===")
    print(f"Environment: {'FROZEN (Packaged)' if path_manager.is_frozen else 'DEVELOPMENT'}")
    print(f"\nPath Manager: {path_manager}")
    print("\n=== Path Information ===")
    
    info = path_manager.get_path_info()
    for key, value in info.items():
        print(f"{key:20}: {value}")
    
    # Test path resolution
    print("\n=== Path Resolution Test ===")
    test_paths = [
        'Config/Config.json',
        'bin/BurnIn/bitwindows.exe',
        'tests/integration/client_pcie_lenovo_storagedv',
    ]
    
    for test_path in test_paths:
        resolved = path_manager.resolve_path(test_path)
        exists = "✓ EXISTS" if resolved.exists() else "✗ NOT FOUND"
        print(f"{test_path:50} -> {exists}")
        print(f"{'':50}    {resolved}")
