@echo off
REM ============================================================
REM  Whim Terminal — Windows 11 Launcher
REM ============================================================

set SCRIPT_DIR=%~dp0
set APP_DIR=%SCRIPT_DIR%..\app
set VENV=%SCRIPT_DIR%..\.venv_win

if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" "%APP_DIR%\whim_windows.py"
) else (
    echo Virtual environment not found. Run setup_windows.bat first.
    echo.
    python "%APP_DIR%\whim_windows.py"
)
