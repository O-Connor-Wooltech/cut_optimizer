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

pyinstaller --noconfirm --name "CutOptimizer" --windowed --clean `
  --hidden-import PySide6.QtSvg `
  --hidden-import PySide6.QtXml `
  run_app.py

Write-Host "Built app in dist/"




