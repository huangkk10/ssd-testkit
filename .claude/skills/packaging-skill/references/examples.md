# Usage Examples

## Example 1: Basic Packaging Workflow

**Scenario**: Package all integration tests into an executable

```powershell
# 1. Navigate to workspace root
cd c:\automation\ssd-testkit

# 2. Activate virtual environment
.venv\Scripts\Activate.ps1

# 3. Navigate to packaging directory
cd packaging

# 4. Build the package
python build.py

# 5. Verify build success
python check_build.py

# 6. Test the executable
cd release\stc1685_burnin
.\run_test.exe --help
```

**Expected Result**: Executable created at `packaging\release\stc1685_burnin\run_test.exe`

## Example 2: Custom Configuration Build

**Scenario**: Package only BurnIN tests with custom version

**Steps**:
1. Edit `packaging/build_config.yaml`:
```yaml
version: "2.1.0"
project_name: "BurnInRunner"
output_folder_name: "burnin_v2"
test_projects_path: "tests/integration/client_pcie_lenovo_storagedv"
```

2. Build:
```powershell
cd packaging
python build.py
```

3. Result: Executable at `packaging\release\burnin_v2\burnin_runner.exe`

## Example 3: Clean Rebuild

**Scenario**: Previous build had errors, need fresh build

```powershell
cd c:\automation\ssd-testkit\packaging

# Clean previous builds
Remove-Item -Recurse -Force build, release -ErrorAction SilentlyContinue

# Rebuild
python build.py

# Verify
python check_build.py
```

## Example 4: Running Packaged Executable with Arguments

**Scenario**: Run specific test project with custom markers

```powershell
cd packaging\release\stc1685_burnin

# Run with default settings
.\run_test.exe

# Run specific project
.\run_test.exe --project client_pcie_lenovo_storagedv

# Run with test markers
.\run_test.exe --project client_pcie_lenovo_storagedv --markers "real"

# Run with multiple markers
.\run_test.exe --markers "real and not timeout"

# Show available options
.\run_test.exe --help
```

## Example 5: Deployment Workflow

**Scenario**: Package tests for deployment to test machines

**Steps**:
1. Build executable:
```powershell
cd c:\automation\ssd-testkit\packaging
python build.py
```

2. Create deployment package:
```powershell
# Compress release folder
Compress-Archive -Path release\stc1685_burnin -DestinationPath BurnInTest_v1.0.zip
```

3. Deploy to test machine:
```powershell
# Copy to target machine (example)
Copy-Item BurnInTest_v1.0.zip \\TestMachine\Tests\
```

4. On test machine:
```powershell
# Extract
Expand-Archive BurnInTest_v1.0.zip -DestinationPath C:\Tests\

# Run
cd C:\Tests\stc1685_burnin
.\run_test.exe
```

## Example 6: Version Control Integration

**Scenario**: Build specific version for release

**Steps**:
1. Update version in `build_config.yaml`:
```yaml
version: "1.2.3"
```

2. Build and tag:
```powershell
# Build
cd packaging
python build.py

# Commit version update
git add build_config.yaml
git commit -m "build: bump version to 1.2.3"
git tag v1.2.3

# Archive release
Compress-Archive -Path release\stc1685_burnin -DestinationPath releases\BurnInTest_v1.2.3.zip
```

## Example 7: Troubleshooting Build

**Scenario**: Build fails, need to debug

```powershell
# Check Python version
python --version

# Verify PyInstaller
pip show pyinstaller

# Check dependencies
pip list

# Review build logs
Get-Content packaging\log\log.err -Tail 50

# Try clean rebuild
Remove-Item -Recurse -Force packaging\build
python packaging\build.py
```

## Example 8: Multiple Build Configurations

**Scenario**: Create different builds for different purposes

**Setup**: Create multiple config files:

`build_config_dev.yaml`:
```yaml
version: "1.0.0-dev"
project_name: "RunTest_Dev"
output_folder_name: "dev_build"
test_projects_path: "tests/integration"
```

`build_config_prod.yaml`:
```yaml
version: "1.0.0"
project_name: "RunTest"
output_folder_name: "production"
test_projects_path: "tests/integration"
```

**Usage**:
```powershell
# Build dev version
Copy-Item build_config_dev.yaml build_config.yaml
python build.py

# Build production version
Copy-Item build_config_prod.yaml build_config.yaml
python build.py
```

## Common Commands Summary

```powershell
# Quick build
cd packaging; python build.py

# Build + verify
cd packaging; python build.py; python check_build.py

# Clean + rebuild
cd packaging; Remove-Item -Recurse -Force build, release; python build.py

# Run executable
cd packaging\release\stc1685_burnin; .\run_test.exe

# Check logs
Get-Content packaging\log\log.txt
Get-Content packaging\log\log.err
```
