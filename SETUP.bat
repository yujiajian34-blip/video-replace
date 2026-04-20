@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

set "PYTHON_CMD="

python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3.10+ was not found.
    echo [INFO] Download and install Python from:
    echo        https://www.python.org/downloads/
    echo [INFO] Make sure "Add Python to PATH" is enabled.
    pause
    exit /b 1
)

echo ========================================
echo   Video Role Replace Tool Setup
echo ========================================
echo Using: %PYTHON_CMD%
echo.

if exist ".venv" if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Found incomplete virtual environment. Recreating...
    rmdir /s /q ".venv"
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment already exists.
)

echo [2/3] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

echo [3/3] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Setup completed successfully.
echo You can now double-click RUN.bat
echo.
pause
exit /b 0
