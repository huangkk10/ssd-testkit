@echo off
:: 檢查是否已有系統管理員權限
net session >nul 2>&1
if %errorlevel% == 0 goto :IS_ADMIN

:: 尚未 elevated，請求 UAC 提升
powershell -Command "Start-Process '%~f0' -Verb RunAs"
exit /b

:IS_ADMIN
set CODE_EXE=%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe
if exist "%CODE_EXE%" (
    start "" "%CODE_EXE%" --no-sandbox "c:\ssd-testkit"
) else (
    echo [ERROR] VS Code not found at: %CODE_EXE%
    pause
)
