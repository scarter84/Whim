# ============================================================
#  Whim Terminal — Windows 11 Setup (PowerShell)
#  Run: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#  Then: .\scripts\setup_windows.ps1
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Whim Terminal — Windows 11 Setup" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# ── Check Python ──
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[ERROR] Python not found." -ForegroundColor Red
    Write-Host "  Install Python 3.10+ from https://python.org" -ForegroundColor Yellow
    Write-Host "  Ensure 'Add Python to PATH' is checked." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Python: $(python --version)" -ForegroundColor Green

# ── Create venv ──
$venvPath = Join-Path $PSScriptRoot "..\.venv_win"
if (-not (Test-Path $venvPath)) {
    Write-Host "`nCreating virtual environment..." -ForegroundColor Cyan
    python -m venv $venvPath
}

# ── Install deps ──
Write-Host "`nInstalling dependencies..." -ForegroundColor Cyan
& "$venvPath\Scripts\pip.exe" install --upgrade pip
& "$venvPath\Scripts\pip.exe" install -r (Join-Path $PSScriptRoot "..\app\requirements_windows.txt")

# ── Create data directories ──
Write-Host "`nCreating data directories..." -ForegroundColor Cyan
$whimData = Join-Path $env:USERPROFILE "Documents\Whim"
$dirs = @(
    "$whimData\Journal",
    "$whimData\Journal\audio_captures",
    "$whimData\ARCHIVE",
    "$whimData\TRANSCRIPT",
    "$whimData\TableReads",
    "$whimData\Incoming",
    "$whimData\voices\personas"
)
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { New-Item -Path $d -ItemType Directory -Force | Out-Null }
}

$ocDir = Join-Path $env:APPDATA "OpenClaw"
$ocFonts = Join-Path $ocDir "WhimUI\fonts"
if (-not (Test-Path $ocFonts)) { New-Item -Path $ocFonts -ItemType Directory -Force | Out-Null }

# ── Check Ollama ──
Write-Host ""
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "[!!] Ollama not found." -ForegroundColor Yellow
    Write-Host "  Install from: https://ollama.com/download/windows" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Ollama found" -ForegroundColor Green
}

# ── Check Tailscale ──
$ts = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $ts) {
    Write-Host "[!!] Tailscale not found (optional)." -ForegroundColor Yellow
    Write-Host "  Install from: https://tailscale.com/download/windows" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Tailscale found" -ForegroundColor Green
}

# ── Create desktop shortcut ──
Write-Host "`nCreating desktop shortcut..." -ForegroundColor Cyan
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Whim Terminal.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path (Resolve-Path $venvPath).Path "Scripts\pythonw.exe"
$shortcut.Arguments = "`"$(Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\app')).Path 'whim_windows.py')`""
$shortcut.WorkingDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..\app")).Path
$shortcut.Description = "Whim Terminal"
$iconPath = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\assets")).Path "fire.png"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Save()
Write-Host "[OK] Desktop shortcut created" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Launch: scripts\launch_whim.bat" -ForegroundColor Cyan
Write-Host "  Or use the desktop shortcut." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
