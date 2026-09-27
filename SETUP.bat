@echo off
setlocal
title Roblox Gaming Launcher - Setup
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py") else (
  where python >nul 2>&1
  if %errorlevel%==0 (set "PY=python") else (
    echo Python 3.11+ was not found.
    echo Install Python and enable "Add Python to PATH".
    pause
    exit /b 1
  )
)
%PY% -m pip install --upgrade pip
%PY% -m pip install -r appequirements.txt
if not exist data mkdir data
echo.
echo Setup complete. Start ROBLOX_LAUNCHER.bat
pause
