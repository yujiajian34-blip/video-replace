@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Python virtual environment not found.
    echo [INFO] Running setup first...
    call "%~dp0SETUP.bat"
    if errorlevel 1 (
        echo.
        echo [ERROR] Setup failed.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import flask, flask_cors, requests" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Required packages are missing.
    echo [INFO] Running setup first...
    call "%~dp0SETUP.bat"
    if errorlevel 1 (
        echo.
        echo [ERROR] Setup failed.
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo   Video Role Replace Tool
echo   URL: http://127.0.0.1:5001
echo   Press Ctrl+C to stop
echo ========================================
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5001"
".venv\Scripts\python.exe" "backend\app.py"

echo.
echo Service stopped.
pause
exit /b 0
