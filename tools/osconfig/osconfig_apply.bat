@echo off
:: Apply OS settings from osconfig.yaml (saves snapshot)
:: Requires Administrator privileges

cd /d "%~dp0..\.."
python tools\osconfig\osconfig_tool.py apply --config tools\osconfig\osconfig.yaml %*
pause
