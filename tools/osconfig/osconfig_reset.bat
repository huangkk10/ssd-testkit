@echo off
:: Reset ALL OS settings to Windows out-of-box defaults (no snapshot needed)
:: Requires Administrator privileges

cd /d "%~dp0..\.."
python tools\osconfig\osconfig_tool.py reset --config tools\osconfig\osconfig_reset.yaml %*
pause
