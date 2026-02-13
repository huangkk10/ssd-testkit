"""
RunTest - SSD-TestKit Test Runner

Main entry point for running packaged pytest tests.
Handles command-line arguments and invokes pytest with proper configuration.
"""

import sys
import os
import argparse
import yaml
from pathlib import Path
from typing import List, Optional

# Import path manager first
from path_manager import path_manager


def get_default_test_project() -> Optional[str]:
    """Get default test project from build_config.yaml."""
    try:
        # In packaged environment, config is in sys._MEIPASS
        # In development, it's in the packaging directory
        if getattr(sys, 'frozen', False):
            # Packaged: look in the extracted temp directory
            config_path = Path(sys._MEIPASS) / 'build_config.yaml'
            print(f"[DEBUG] Looking for config in packaged env: {config_path}")
        else:
            # Development: look in packaging directory
            config_path = Path(__file__).parent / 'build_config.yaml'
            print(f"[DEBUG] Looking for config in dev env: {config_path}")
        
        print(f"[DEBUG] Config file exists: {config_path.exists()}")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                test_projects = config.get('test_projects', [])
                if test_projects:
                    # Return first test project
                    print(f"[DEBUG] Found default test project: {test_projects[0]}")
                    return test_projects[0]
                else:
                    print("[DEBUG] No test_projects found in config")
    except Exception as e:
        print(f"Warning: Failed to load default test project: {e}")
        import traceback
        traceback.print_exc()
    return None


def setup_environment():
    """Setup environment variables and paths."""
    # Set working directory to app directory
    os.chdir(str(path_manager.app_dir))
    
    # Ensure log directories exist
    log_dir = path_manager.get_log_dir()
    testlog_dir = path_manager.get_testlog_dir()
    
    # Print environment info
    print("=" * 70)
    print("SSD-TestKit Test Runner")
    print("=" * 70)
    print(f"Environment: {'PACKAGED' if path_manager.is_frozen else 'DEVELOPMENT'}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"App Directory: {path_manager.app_dir}")
    print(f"Log Directory: {log_dir}")
    print(f"TestLog Directory: {testlog_dir}")
    print("-" * 70)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='SSD-TestKit Test Runner - Run pytest tests from packaged executable',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run specific test file
  %(prog)s --test tests\\integration\\client_pcie_lenovo_storagedv\\stc1685_burnin\\test_main.py
  
  # Run specific test class
  %(prog)s --test tests\\integration\\client_pcie_lenovo_storagedv\\stc1685_burnin\\test_main.py::TestSTC1685BurnIN
  
  # Run with markers
  %(prog)s --test tests\\integration --markers "client_lenovo and feature_burnin"
  
  # Verbose output
  %(prog)s --test tests\\integration\\client_pcie_lenovo_storagedv\\stc1685_burnin\\test_main.py -v
  
  # Show path information
  %(prog)s --show-paths
        '''
    )
    
    # Main test argument
    parser.add_argument(
        '--test', '-t',
        type=str,
        help='Test file, directory, or test class to run (e.g., tests/integration/...)'
    )
    
    # pytest options
    parser.add_argument(
        '--markers', '-m',
        type=str,
        help='pytest marker expression (e.g., "slow", "client_lenovo and feature_burnin")'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to config file (optional)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='Increase verbosity (can be used multiple times: -v, -vv, -vvv)'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    # Output options
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output directory for test results (default: ./testlog)'
    )
    
    parser.add_argument(
        '--report',
        type=str,
        choices=['none', 'term', 'html'],
        default='term',
        help='Test report format (default: term)'
    )
    
    # Utility options
    parser.add_argument(
        '--show-paths',
        action='store_true',
        help='Show path information and exit'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show pytest command without executing'
    )
    
    parser.add_argument(
        '--pytest-args',
        type=str,
        nargs=argparse.REMAINDER,
        help='Additional arguments to pass directly to pytest'
    )
    
    return parser.parse_args()


def show_path_information():
    """Display path information for debugging."""
    print("\n" + "=" * 70)
    print("PATH INFORMATION")
    print("=" * 70)
    
    info = path_manager.get_path_info()
    for key, value in info.items():
        status = ""
        if value and key.endswith('_dir'):
            path = Path(value)
            status = " [EXISTS]" if path.exists() else " [NOT FOUND]"
        print(f"{key:20}: {value}{status}")
    
    print("=" * 70)


def build_pytest_args(args: argparse.Namespace) -> List[str]:
    """
    Build pytest command-line arguments.
    
    Args:
        args: Parsed command-line arguments
    
    Returns:
        List of pytest arguments
    """
    pytest_args = []
    
    # Add test path
    if args.test:
        test_path = path_manager.resolve_path(args.test)
        pytest_args.append(str(test_path))
    else:
        # Default to tests directory
        pytest_args.append(str(path_manager.get_tests_dir()))
    
    # Add pytest.ini if exists
    pytest_ini = path_manager.get_pytest_ini()
    if pytest_ini:
        pytest_args.extend(['-c', str(pytest_ini)])
    
    # Add markers
    if args.markers:
        pytest_args.extend(['-m', args.markers])
    
    # Add verbosity
    if args.verbose > 0:
        pytest_args.append('-' + 'v' * args.verbose)
    
    # Add output directory
    output_dir = args.output if args.output else str(path_manager.get_testlog_dir())
    pytest_args.extend(['--basetemp', output_dir])
    
    # Add log file output (in addition to console)
    log_file = path_manager.get_log_dir() / 'pytest.log'
    pytest_args.extend(['--log-file', str(log_file)])
    pytest_args.append('--log-file-level=INFO')
    
    # Add report options
    if args.report == 'html':
        report_path = Path(output_dir) / 'report.html'
        pytest_args.extend(['--html', str(report_path), '--self-contained-html'])
    
    # Show test execution progress
    pytest_args.append('-s')  # Don't capture output
    
    # Show test durations
    pytest_args.append('--durations=10')
    
    # Add any extra pytest arguments
    if args.pytest_args:
        pytest_args.extend(args.pytest_args)
    
    return pytest_args


def run_pytest(pytest_args: List[str], dry_run: bool = False) -> int:
    """
    Run pytest with given arguments.
    
    Args:
        pytest_args: List of pytest arguments
        dry_run: If True, only show command without executing
    
    Returns:
        pytest exit code (0 = success, non-zero = failure)
    """
    print("\n" + "=" * 70)
    print("PYTEST COMMAND")
    print("=" * 70)
    print(f"pytest {' '.join(pytest_args)}")
    print("=" * 70 + "\n")
    
    if dry_run:
        print("[DRY RUN] Would execute pytest with above arguments")
        return 0
    
    # Import pytest and run
    try:
        import pytest
        exit_code = pytest.main(pytest_args)
        return exit_code
    except ImportError as e:
        print(f"ERROR: Failed to import pytest: {e}")
        print("Make sure pytest is installed: pip install pytest")
        return 1
    except Exception as e:
        print(f"ERROR: pytest execution failed: {e}")
        return 1


def main() -> int:
    """
    Main entry point.
    
    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    # Setup environment
    setup_environment()
    
    # Parse arguments
    args = parse_arguments()
    
    # Show path information if requested
    if args.show_paths:
        show_path_information()
        return 0
    
    # Get test target: use --test if provided, otherwise use default from config
    test_target = args.test
    if not test_target:
        test_target = get_default_test_project()
        if test_target:
            print(f"Using default test project: {test_target}")
            # Update args.test for build_pytest_args
            args.test = test_target
        else:
            print("ERROR: No test specified and no default test project found")
            print("Either provide --test argument or configure test_projects in build_config.yaml")
            print("Use --help for usage information")
            return 1
    
    # Build pytest arguments
    pytest_args = build_pytest_args(args)
    
    # Run pytest
    exit_code = run_pytest(pytest_args, dry_run=args.dry_run)
    
    # Print summary
    print("\n" + "=" * 70)
    if exit_code == 0:
        print("✓ TESTS PASSED")
    else:
        print(f"✗ TESTS FAILED (exit code: {exit_code})")
    print("=" * 70 + "\n")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
