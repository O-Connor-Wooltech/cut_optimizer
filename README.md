# Cut Optimizer (1D) — MVP (Python + PySide6)

Cross-platform desktop app to generate a cut plan for 1D stock lengths (units **mm**).

Features:
- Stock input: length + qty
- Parts input: length + qty + optional label
- Kerf (blade width) in mm
- Import CSV/XLSX
- Export plan CSV + summary + unallocated
- UI table editing

## Run

```powershell
python -m venv .venv
# If activation is blocked, just use .venv\Scripts\python.exe directly (see below)

.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m cut_optimizer
```

## Input formats

### Stock
Columns: `stock_length`, `qty`

### Parts
Columns: `part_length`, `qty`, optional `label`

## Build (Windows/macOS)

PyInstaller expects a **script file** entrypoint. We provide `run_app.py`.

Windows (PowerShell):
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
scripts\build_windows.ps1
```

macOS/Linux:
```bash
python -m pip install -r requirements.txt
./scripts/build_macos.sh
```


## Kerf decimals
Kerf supports decimals like **2.8mm**. Internally the app uses **0.1mm units** so results remain stable.


## Output includes labels
The cut plan lists each cut as `length label` (e.g. `1350 Rail`). Labels come from the Parts input `label` column.
