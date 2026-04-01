@echo off
:: Revert OS settings to the state captured at last apply
:: Requires Administrator privileges

cd /d "%~dp0..\.."
python tools\osconfig\osconfig_tool.py revert %*
pause
