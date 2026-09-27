@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py") else (where python >nul 2>&1 && set "PY=python")
if not defined PY (echo Python 3.11+ not found. Install Python and enable PATH.&pause&exit /b 1)
%PY% -m pip install --upgrade pip
%PY% -m pip install -r app\requirements.txt
if not exist data mkdir data
echo Setup complete. Run ROBLOX_LAUNCHER.bat
pause
