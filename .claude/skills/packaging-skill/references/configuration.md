# PyInstaller Configuration Reference

## build_config.yaml Structure

**Location**: `c:\automation\ssd-testkit\packaging\build_config.yaml`

```yaml
version: "1.0.0"
project_name: "RunTest"
output_folder_name: "stc1685_burnin"
test_projects_path: "tests/integration"
```

## Configuration Parameters

### version
- **Type**: String
- **Description**: Package version number
- **Example**: `"1.0.0"`, `"2.1.5"`
- **Usage**: Appears in build logs and helps track releases

### project_name
- **Type**: String  
- **Description**: Name of the output executable file (without .exe extension)
- **Example**: `"RunTest"`  generates `run_test.exe`
- **Note**: Will be converted to snake_case for the executable filename

### output_folder_name
- **Type**: String
- **Description**: Folder name inside the `release/` directory
- **Example**: `"stc1685_burnin"`  creates `packaging/release/stc1685_burnin/`
- **Usage**: Organizes different build variants

### test_projects_path
- **Type**: String (relative path)
- **Description**: Path to test projects to include in the package
- **Example**: `"tests/integration"`, `"tests/unit"`
- **Note**: Path is relative to workspace root (`c:\automation\ssd-testkit`)

## Customization Examples

### Example 1: Different Test Suite
```yaml
version: "2.0.0"
project_name: "UnitTestRunner"
output_folder_name: "unit_tests"
test_projects_path: "tests/unit"
```

### Example 2: Specific Project
```yaml
version: "1.0.0"
project_name: "BurnInTest"
output_folder_name: "burnin_only"
test_projects_path: "tests/integration/client_pcie_lenovo_storagedv"
```

## Output Structure

After building, the release structure will be:
```
packaging/
 release/
     {output_folder_name}/
         {project_name}.exe
         Config/              # Configuration files
         tests/               # Test projects from test_projects_path
         _internal/           # PyInstaller dependencies
```
