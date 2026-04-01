@echo off
:: Show current OS configuration status vs osconfig.yaml targets (read-only)

cd /d "%~dp0..\.."
python tools\osconfig\osconfig_tool.py status --config tools\osconfig\osconfig.yaml %*
pause
