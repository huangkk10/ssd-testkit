@echo off
cd /d c:\ssd-testkit\tests\integration\test_case\stc2557_adk_s3s4s5

:: -- Phase 2: BPFS Fast-Startup guard --
:: FAS.exe is alive during BPFS training iterations; exit to avoid
:: launching a second pytest that conflicts with the ongoing assessment.
tasklist /FI "IMAGENAME eq FAS.exe" /NH 2>nul | find /i "FAS.exe" >nul 2>&1
if not errorlevel 1 (
    echo [AutoRun] FAS.exe detected - BPFS resume, exiting
    exit /b 0
)

:: -- Phase 3: Stale-lock guard --
:: If the lock exists but python.exe is gone the lock is stale; clear it.
set LOCK=c:\ssd-testkit\tests\integration\test_case\stc2557_adk_s3s4s5\.pytest_running.lock
if exist "%LOCK%" (
    tasklist /FI "IMAGENAME eq python.exe" /NH 2>nul | find /i "python.exe" >nul 2>&1
    if errorlevel 1 (
        echo [AutoRun] Stale lock detected - clearing
        del "%LOCK%" 2>nul
    ) else (
        echo [AutoRun] pytest already running - skipping
        exit /b 0
    )
)
echo %TIME% > "%LOCK%"

set PYTEST_REBOOT_RECOVERY=1

"C:\ssd-testkit\.venv\Scripts\python.exe" -m pytest -v --tb=short "c:\ssd-testkit\tests\integration\test_case\stc2557_adk_s3s4s5\test_main.py"

del "%LOCK%" 2>nul
