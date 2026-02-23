---
name: packaging-skill
description: Build Python test scripts into standalone executables using PyInstaller. Use when user asks to package tests, create executable, build exe, or mentions pyinstaller, 打包, or deploying tests as portable executables.
---

# PyInstaller Packaging Skill

Package Python test scripts into standalone Windows executables using PyInstaller configuration.

## Prerequisites

- Python 3.10 or higher
- PyInstaller 6.18.0 or higher
- Virtual environment activated at ``c:\automation\ssd-testkit\.venv``
- Working directory: ``c:\automation\ssd-testkit``

## Quick Start

````powershell
# Navigate to packaging directory
cd c:\automation\ssd-testkit\packaging

# Build executable
python build.py

# Verify build
python check_build.py

# Run the executable
cd release\stc1685_burnin
.\run_test.exe
````

## Configuration

Edit ``packaging/build_config.yaml`` to customize the build:

````yaml
version: "1.0.0"              # Package version
project_name: "RunTest"        # Executable name (becomes run_test.exe)
output_folder_name: "stc1685_burnin"  # Release folder name
test_projects_path: "tests/integration"  # Tests to include
````

**For detailed configuration options**, see ``references/configuration.md``

## Build Workflow

### Standard Build
````powershell
cd packaging
python build.py
````

### Clean Rebuild
````powershell
cd packaging
Remove-Item -Recurse -Force build, release -ErrorAction SilentlyContinue
python build.py
````

### Verify Build Success
````powershell
python check_build.py
````

## Output Structure

After building, find your executable in:
````
packaging/release/{output_folder_name}/
 {project_name}.exe    # Main executable
 Config/               # Test configuration files
 tests/                # Test projects
 _internal/            # PyInstaller dependencies
````

## Running the Executable

### Basic Execution
````powershell
cd packaging\release\stc1685_burnin
.\run_test.exe
````

### With Arguments
````powershell
# Run specific project
.\run_test.exe --project client_pcie_lenovo_storagedv

# Run with test markers
.\run_test.exe --markers "real"

# Show help
.\run_test.exe --help
````

## Common Scenarios

**For detailed examples**, see ``references/examples.md``

### Scenario 1: Package All Tests
````powershell
cd packaging
python build.py
````

### Scenario 2: Package Specific Tests
1. Edit ``build_config.yaml``  change ``test_projects_path``
2. Run ``python build.py``

### Scenario 3: Create Deployment Package
````powershell
cd packaging
python build.py
Compress-Archive -Path release\stc1685_burnin -DestinationPath BurnInTest.zip
````

## Troubleshooting

**For comprehensive troubleshooting**, see ``references/troubleshooting.md``

### Build Fails
1. Check Python version: ``python --version`` (need 3.10+)
2. Verify PyInstaller: ``pip show pyinstaller`` (need 6.18.0+)
3. Review logs: ``Get-Content packaging\log\log.err``

### Executable Won't Run
1. Run from command prompt to see errors
2. Check Config files exist in release folder
3. Verify test_projects_path is correct in build_config.yaml

### Missing Dependencies
````powershell
# Ensure virtual environment is activated
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
````

## Related Files

- **Build Script**: ``packaging/build.py`` - Main build automation
- **Config File**: ``packaging/build_config.yaml`` - Build settings
- **Verification**: ``packaging/check_build.py`` - Validate build output
- **Test Runner**: ``packaging/run_test.py`` - Entry point for executable
- **PyInstaller Spec**: ``packaging/run_test.spec`` - PyInstaller configuration
- **Chinese Docs**: ``packaging/README.md`` - Detailed Chinese documentation

## Integration Points

The packaged executable integrates with:
- **Test Framework**: ``framework/base_test.py`` - BaseTestCase and utilities
- **Logger**: ``lib/logger.py`` - Centralized logging system
- **BurnIN**: ``lib/testtool/burnin/controller.py`` - Burn-in test controller
- **SmartCheck**: ``lib/testtool/smartcheck/controller.py`` - SMART verification

## Important Notes

- Build time: 2-5 minutes depending on project size
- Executable size: ~50-100MB with all dependencies
- Each build overwrites previous release folder
- Build logs saved in ``packaging/log/`` directory
- Virtual environment must be activated before building
- Windows-only: Generates .exe files for Windows systems
