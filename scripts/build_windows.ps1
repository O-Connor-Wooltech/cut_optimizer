# PowerShell build script
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

pyinstaller --noconfirm --name "CutOptimizer" --windowed --clean `
  --hidden-import PySide6.QtSvg `
  --hidden-import PySide6.QtXml `
  run_app.py

Write-Host "Built app in dist/"
