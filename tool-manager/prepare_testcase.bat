@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0prepare_testcase.ps1" %*
