@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0upload_tools_to_nexus.ps1" %*
