@echo off
chcp 65001 > nul
setlocal

:: ============================================================
:: SSD-TestKit One-Click Build Script
:: Usage:
::   build.bat              - Normal build (reuse existing spec)
::   build.bat --clean      - Clean build artifacts first
::   build.bat --no-release - Skip ZIP creation
::   build.bat --spec-only  - Generate spec file only (no EXE)
::   build.bat --new-spec   - Force regenerate spec from template
:: ============================================================

:: Move to the packaging directory (same folder as this .bat)
cd /d "%~dp0"

:: ── Check Python ────────────────────────────────────────────
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python and add it to PATH.
    pause
    exit /b 1
)

:: ── Check PyInstaller ───────────────────────────────────────
python -c "import PyInstaller" > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller not found.
    echo         Please run:  pip install pyinstaller
    pause
    exit /b 1
)

:: ── Handle --new-spec flag (delete spec so it gets regenerated) ──
set ARGS=%*
echo %ARGS% | findstr /i "\-\-new-spec" > nul
if %errorlevel% equ 0 (
    if exist run_test.spec (
        echo [INFO] Removing existing run_test.spec for regeneration...
        del /f /q run_test.spec
    )
    :: Remove --new-spec from args before passing to build.py
    set ARGS=%ARGS:--new-spec=%
)

:: ── Run build.py ────────────────────────────────────────────
echo.
python build.py %ARGS%
set BUILD_EXIT=%errorlevel%

echo.
if %BUILD_EXIT% equ 0 (
    echo ============================================================
    echo  Build succeeded!
    echo  Output: dist\
    echo ============================================================
) else (
    echo ============================================================
    echo  Build FAILED (exit code: %BUILD_EXIT%)
    echo  Check build_output above for details.
    echo ============================================================
)

endlocal
pause
exit /b %BUILD_EXIT%
