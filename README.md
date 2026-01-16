# Cut Optimizer (1D) — MVP (Python + PySide6)

Cross-platform desktop app to generate a cut plan for 1D stock lengths (units **mm**).

## Features

- Stock input: length + qty
- Parts input: length + qty + optional label
- Kerf (blade width) in mm (supports decimals like **2.8**)
- Import CSV / XLSX
- Lengths rounded **up** to the next **0.5mm** increment (stock + parts)
- Export plan:
  - CSV (plan + separate summary + unallocated)
  - PDF (multi-page, cuts vertical + sticks horizontal)
- UI table editing

---

## Quick start (all platforms)

1. Install **Python 3** and **Git**
2. Clone this repo
3. Create a virtual environment
4. Install requirements
5. Run the app

---

## Windows setup (PowerShell)

### 1) Install prerequisites
- Install **Python 3** from https://www.python.org/downloads/windows/
  - ✅ tick **“Add python.exe to PATH”**
- Install **Git** from https://git-scm.com/download/win

### 2) Clone
```powershell
git clone https://github.com/O-Connor-Wooltech/cut_optimizer.git
cd cut_optimizer
```

### 3) Create a venv
```powershell
python -m venv .venv
```

### 4) Install dependencies
If your PowerShell activation is blocked, you can skip activation and call the venv python directly:

```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 5) Run
```powershell
.venv\Scripts\python.exe -m cut_optimizer
```

---

## macOS setup (Terminal)

### 1) Install prerequisites
- Install **Git** (usually already present)
- Install Python 3 (recommended via Homebrew):
```bash
brew install python
```

### 2) Clone
```bash
git clone https://github.com/O-Connor-Wooltech/cut_optimizer.git
cd cut_optimizer
```

### 3) Create + activate venv
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4) Install dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5) Run
```bash
python -m cut_optimizer
```

---

## Linux setup (Ubuntu/Debian example)

### 1) Install prerequisites
```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

### 2) Clone
```bash
git clone https://github.com/O-Connor-Wooltech/cut_optimizer.git
cd cut_optimizer
```

### 3) Create + activate venv
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4) Install dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5) Run
```bash
python -m cut_optimizer
```

> If you hit Qt errors on Linux (e.g. “Could not load the Qt platform plugin xcb”), install common runtime deps:
>
> Ubuntu/Debian:
> ```bash
> sudo apt install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
> ```

---

## Input formats

All lengths are **mm**.

**Rounding rule:** all entered/imported lengths (stock + parts) are rounded **up** to the next **0.5mm**.
So `1000.01` becomes `1000.5`, and `1000.6` becomes `1001.0`.

> Note: stock/part lengths may be integers or decimals. They are rounded **up** to the next **0.5mm** boundary.

### Stock CSV/XLSX
Columns:
- `stock_length` (number)
- `qty` (integer)

Example:
```csv
stock_length,qty
6000,10
7500,4
```

### Parts CSV/XLSX
Columns:
- `part_length` (number)
- `qty` (integer)
- `label` (optional string)

Example:
```csv
part_length,qty,label
1350,8,Rail
450,16,Stiffener
1000.2,4,Bracket (will round to 1000.5)
```

> Tip: check the `samples/` folder for example inputs.

---

## Output

The app exports:
- **Cut plan CSV** (one row per stick with a `cuts` list)
  - Columns: `stick_no`, `stock_length_mm`, `cuts`, `used_mm`, `leftover_mm`, `utilization_pct`
- **Summary CSV** (`.summary.csv`)
- **Unallocated parts CSV** (`.unallocated.csv`, if any)
- **Cut plan PDF** (multi-page table: cut # rows, stick columns, wraps stick columns as needed)

---

## Kerf decimals

Kerf supports decimals like **2.8mm**. Internally the app uses 0.1mm units so results remain stable.

---

## Build (PyInstaller)

PyInstaller expects a script entrypoint — this repo provides `run_app.py`.

### Windows (PowerShell)
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
scripts\build_windows.ps1
```

### macOS / Linux (bash)
```bash
python -m pip install -r requirements.txt
./scripts/build_macos.sh
```

### Manual build (all platforms)
If you prefer running PyInstaller directly, you can use the provided spec file:
```bash
python -m pip install pyinstaller
pyinstaller CutOptimizer.spec
```

---

## Development notes

- Run from source:
  - Windows: `.venv\Scripts\python.exe -m cut_optimizer`
  - macOS/Linux: `python -m cut_optimizer`
- Build artifacts typically land under `dist/` (PyInstaller default)

---

## About

Tool to optimise the cutting of length of material.
