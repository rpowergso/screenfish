@echo off
setlocal
cd /d "%~dp0"
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    echo Install 64-bit Python for Windows with Tcl/Tk and add it to PATH.
    echo See README.md for setup instructions.
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0ScreenFish.pyw"
