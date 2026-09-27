@echo off
cd /d "%~dp0"
where py >nul 2>&1 && set "PY=py"
if not defined PY set "PY=python"
%PY% app\main.py
if errorlevel 1 pause
