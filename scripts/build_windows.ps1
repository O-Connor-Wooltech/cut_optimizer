# PowerShell build script
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

$distPath = Join-Path $PSScriptRoot "..\dist"

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path $distPath) {
    # If you run the built EXE during testing, it can lock DLL/PYD files
    Get-Process CutOptimizer -ErrorAction SilentlyContinue | Stop-Process -Force

    for ($i = 0; $i -lt 10; $i++) {
        try {
            Remove-Item -LiteralPath $distPath -Recurse -Force -ErrorAction Stop
            break
        } catch {
            Start-Sleep -Milliseconds 500
            if ($i -eq 9) { throw }
        }
    }
}

# On Windows, the "pyinstaller.exe" console-script launcher can embed an absolute path
# to the Python interpreter from when it was first installed. If the project folder was
# moved/renamed (or a .venv was copied), this can break with:
#   "Fatal error in launcher: Unable to create process using ..."
# Running PyInstaller as a module avoids that launcher entirely.
python -m PyInstaller --noconfirm --name "CutOptimizer" --windowed --clean `
  --hidden-import PySide6.QtSvg `
  --hidden-import PySide6.QtXml `
  run_app.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Built app in dist/"
