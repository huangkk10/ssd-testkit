# Troubleshooting Guide

## Build Failures

### Error: Python version incompatible
**Symptom**: Build fails with version-related errors

**Solution**:
```powershell
python --version  # Must show Python 3.10 or higher
```

If version is wrong, activate the correct virtual environment:
```powershell
.venv\Scripts\Activate.ps1
```

### Error: PyInstaller not found
**Symptom**: `ModuleNotFoundError: No module named 'PyInstaller'`

**Solution**:
```powershell
pip show pyinstaller  # Check if installed
pip install pyinstaller>=6.18.0  # Install if missing
```

### Error: Build fails with import errors
**Symptom**: PyInstaller can't find certain modules

**Solution**:
1. Check all dependencies are installed:
   ```powershell
   pip install -r requirements.txt
   ```

2. Review build logs:
   ```powershell
   Get-Content packaging\log\log.err
   ```

3. Add missing modules to `requirements.txt` if needed

## Executable Issues

### Error: Executable doesn't start
**Symptom**: Double-clicking `run_test.exe` does nothing or crashes immediately

**Solution**:
1. Run from command prompt to see error messages:
   ```powershell
   cd packaging\release\stc1685_burnin
   .\run_test.exe
   ```

2. Check if Config files are present:
   ```powershell
   Get-ChildItem Config
   ```

3. Verify test_projects_path in `build_config.yaml` points to valid directory

### Error: Missing dependencies at runtime
**Symptom**: `ImportError` or `DLL not found` when running executable

**Solution**:
1. Check `_internal/` folder contains all necessary DLLs
2. Rebuild with verbose logging

### Error: Test files not found
**Symptom**: Executable runs but can't find test files

**Solution**:
1. Verify `tests/` folder exists in release directory
2. Check `test_projects_path` in `build_config.yaml` is correct
3. Ensure test files were copied during build (check build logs)

## Build Performance

### Issue: Build takes too long
**Typical Time**: 2-5 minutes for normal project

**Optimization**:
1. Clean build artifacts before rebuilding
2. Exclude unnecessary test files by adjusting `test_projects_path`

### Issue: Executable size too large
**Typical Size**: 50-100 MB

**Optimization**:
1. Review included dependencies in `requirements.txt`
2. Consider using `--exclude-module` in PyInstaller spec if certain modules aren't needed
3. Remove unnecessary test projects from `test_projects_path`

## Log File Analysis

### Check Build Logs
```powershell
# Standard output
Get-Content packaging\log\log.txt

# Error output
Get-Content packaging\log\log.err
```

### Common Log Messages

**"WARNING: lib not found"**
- Usually safe to ignore unless executable fails to run
- May indicate optional dependency is missing

**"ERROR: import of module failed"**
- Critical issue - build may succeed but executable will fail
- Fix by ensuring module is installed in virtual environment

**"INFO: Building EXE from EXE-00.toc completed successfully"**
- Build completed successfully
- Check `packaging\release\` for output

## Getting Help

If issues persist:
1. Check PyInstaller version: `pip show pyinstaller`
2. Review Python version: `python --version`
3. Verify virtual environment is activated
4. Check all paths in `build_config.yaml` are correct
5. Review complete error logs in `packaging/log/log.err`
