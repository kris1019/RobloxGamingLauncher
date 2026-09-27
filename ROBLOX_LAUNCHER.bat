@echo off
setlocal
title Roblox Gaming Launcher
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py") else (set "PY=python")
%PY% app\main.py
if errorlevel 1 (
    echo.
    echo Launcher exited with an error.
    pause
)
