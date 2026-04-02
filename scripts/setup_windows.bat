@echo off
REM ============================================================
REM  Whim Terminal — Windows 11 Setup Script
REM  Run this once after cloning the repository.
REM ============================================================

echo.
echo ============================================================
echo   Whim Terminal — Windows 11 Setup
echo ============================================================
echo.

REM ── Check Python ──
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    echo         Make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

echo [OK] Python found
python --version

REM ── Create virtual environment ──
if not exist "%~dp0..\.venv_win" (
    echo.
    echo Creating virtual environment...
    python -m venv "%~dp0..\.venv_win"
)

REM ── Activate and install deps ──
echo.
echo Installing dependencies...
call "%~dp0..\.venv_win\Scripts\activate.bat"
pip install --upgrade pip
pip install -r "%~dp0..\app\requirements_windows.txt"

REM ── Create Whim data directories ──
echo.
echo Creating data directories...
set WHIM_DATA=%USERPROFILE%\Documents\Whim
if not exist "%WHIM_DATA%\Journal" mkdir "%WHIM_DATA%\Journal"
if not exist "%WHIM_DATA%\Journal\audio_captures" mkdir "%WHIM_DATA%\Journal\audio_captures"
if not exist "%WHIM_DATA%\ARCHIVE" mkdir "%WHIM_DATA%\ARCHIVE"
if not exist "%WHIM_DATA%\TRANSCRIPT" mkdir "%WHIM_DATA%\TRANSCRIPT"
if not exist "%WHIM_DATA%\TableReads" mkdir "%WHIM_DATA%\TableReads"
if not exist "%WHIM_DATA%\Incoming" mkdir "%WHIM_DATA%\Incoming"
if not exist "%WHIM_DATA%\voices\personas" mkdir "%WHIM_DATA%\voices\personas"

REM ── Create OpenClaw config directory ──
set OC_DIR=%APPDATA%\OpenClaw
if not exist "%OC_DIR%" mkdir "%OC_DIR%"
if not exist "%OC_DIR%\WhimUI\fonts" mkdir "%OC_DIR%\WhimUI\fonts"

REM ── Check Ollama ──
echo.
where ollama >nul 2>&1
if errorlevel 1 (
    echo [!!] Ollama not found. Install from: https://ollama.com/download/windows
    echo      Whim will start but AI features need Ollama running.
) else (
    echo [OK] Ollama found
)

REM ── Check Tailscale ──
where tailscale >nul 2>&1
if errorlevel 1 (
    echo [!!] Tailscale not found. Install from: https://tailscale.com/download/windows
    echo      Optional — needed only for direct mesh connectivity to mobile devices.
) else (
    echo [OK] Tailscale found
)

echo.
echo ============================================================
echo   Setup complete!
echo.
echo   To launch Whim Terminal:
echo     cd app
echo     ..\..venv_win\Scripts\python whim_windows.py
echo.
echo   Or use the launcher:
echo     scripts\launch_whim.bat
echo ============================================================
echo.
pause
