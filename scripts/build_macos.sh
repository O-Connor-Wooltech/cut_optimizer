#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

rm -rf build dist

pyinstaller --noconfirm --name "CutOptimizer" --windowed --clean \
  --hidden-import PySide6.QtSvg \
  --hidden-import PySide6.QtXml \
  run_app.py

echo "Built app in dist/"
