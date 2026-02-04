from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets, QtGui

from .models import StockTableModel, PartsTableModel
from .io_utils import load_stock_table, load_parts_table, export_plan_csv, export_plan_pdf
from .optimizer import optimize_cut_order, OptimizeResult, u_to_mm_str, SCALE

def _icon_path() -> Path:
    # Works in dev and in PyInstaller onefile/onedir builds
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base / "cut_optimizer" / "assets" / "app_icon.png"
    return Path(__file__).resolve().parent / "assets" / "app_icon.png"

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Cut Optimizer (mm) — MVP")
        self.resize(1100, 700)

        self.stock_model = StockTableModel([])
        self.parts_model = PartsTableModel([])

        # Kerf supports decimals like 2.8mm (step 0.1mm)
        self.kerf_spin = QtWidgets.QDoubleSpinBox()
        self.kerf_spin.setRange(0.0, 1000.0)
        self.kerf_spin.setDecimals(1)
        self.kerf_spin.setSingleStep(0.1)
        self.kerf_spin.setValue(2.8)
        self.kerf_spin.setSuffix(" mm")

        self.status_box = QtWidgets.QPlainTextEdit()
        self.status_box.setReadOnly(True)

        self.stock_view = QtWidgets.QTableView()
        self.stock_view.setModel(self.stock_model)
        self.stock_view.horizontalHeader().setStretchLastSection(True)
        self.stock_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self.parts_view = QtWidgets.QTableView()
        self.parts_view.setModel(self.parts_model)
        self.parts_view.horizontalHeader().setStretchLastSection(True)
        self.parts_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self.plan_view = QtWidgets.QTableWidget()
        self.plan_view.setColumnCount(6)
        self.plan_view.setHorizontalHeaderLabels(
            ["Stick #", "Stock (mm)", "Cuts (mm + label)", "Used (mm)", "Leftover (mm)", "Util (%)"]
        )
        self.plan_view.horizontalHeader().setStretchLastSection(True)
        self.plan_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.btn_load_stock = QtWidgets.QPushButton("Load Stock (CSV/XLSX)")
        self.btn_load_parts = QtWidgets.QPushButton("Load Parts (CSV/XLSX)")
        self.btn_add_stock = QtWidgets.QPushButton("Add Stock Row")
        self.btn_del_stock = QtWidgets.QPushButton("Delete Stock Row(s)")
        self.btn_add_part = QtWidgets.QPushButton("Add Part Row")
        self.btn_del_part = QtWidgets.QPushButton("Delete Part Row(s)")
        self.btn_optimize = QtWidgets.QPushButton("Optimize")
        self.btn_export = QtWidgets.QPushButton("Export Plan (CSV)")
        self.btn_export.setEnabled(False)

        self.btn_export_pdf = QtWidgets.QPushButton("Export Plan (PDF)")
        self.btn_export_pdf.setEnabled(False)

        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addWidget(QtWidgets.QLabel("Kerf:"))
        top_bar.addWidget(self.kerf_spin)
        top_bar.addStretch(1)
        top_bar.addWidget(self.btn_optimize)
        top_bar.addWidget(self.btn_export)
        top_bar.addWidget(self.btn_export_pdf)

        stock_btns = QtWidgets.QHBoxLayout()
        stock_btns.addWidget(self.btn_load_stock)
        stock_btns.addWidget(self.btn_add_stock)
        stock_btns.addWidget(self.btn_del_stock)
        stock_btns.addStretch(1)

        parts_btns = QtWidgets.QHBoxLayout()
        parts_btns.addWidget(self.btn_load_parts)
        parts_btns.addWidget(self.btn_add_part)
        parts_btns.addWidget(self.btn_del_part)
        parts_btns.addStretch(1)

        left = QtWidgets.QVBoxLayout()
        left.addWidget(QtWidgets.QLabel("Stock (length + qty)"))
        left.addLayout(stock_btns)
        left.addWidget(self.stock_view, stretch=2)
        left.addSpacing(8)
        left.addWidget(QtWidgets.QLabel("Parts to cut (length + qty + optional label)"))
        left.addLayout(parts_btns)
        left.addWidget(self.parts_view, stretch=3)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(QtWidgets.QLabel("Optimized cut plan"))
        right.addWidget(self.plan_view, stretch=4)
        right.addWidget(QtWidgets.QLabel("Status / summary"))
        right.addWidget(self.status_box, stretch=2)

        splitter = QtWidgets.QSplitter()
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left)
        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(top_bar)
        layout.addWidget(splitter)
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._last_result: Optional[OptimizeResult] = None
        self._parts_source_path: Optional[str] = None

        self.btn_load_stock.clicked.connect(self.on_load_stock)
        self.btn_load_parts.clicked.connect(self.on_load_parts)
        self.btn_add_stock.clicked.connect(lambda: self.stock_model.add_row())
        self.btn_add_part.clicked.connect(lambda: self.parts_model.add_row())
        self.btn_del_stock.clicked.connect(self.on_delete_stock)
        self.btn_del_part.clicked.connect(self.on_delete_parts)
        self.btn_optimize.clicked.connect(self.on_optimize)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_export_pdf.clicked.connect(self.on_export_pdf)

    def log(self, msg: str) -> None:
        self.status_box.appendPlainText(msg)

    def _pick_file(self, title: str, filters: str) -> Optional[str]:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, title, "", filters)
        return path or None

    def on_load_stock(self) -> None:
        path = self._pick_file("Load Stock", "Data Files (*.csv *.xlsx *.xls)")
        if not path:
            return
        try:
            items = load_stock_table(path)
            self.stock_model.set_rows(items)
            self.log(f"Loaded stock from: {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load error", str(e))

    def on_load_parts(self) -> None:
        path = self._pick_file("Load Parts", "Data Files (*.csv *.xlsx *.xls)")
        if not path:
            return
        try:
            items = load_parts_table(path)
            self.parts_model.set_rows(items)
            self._parts_source_path = path
            self.log(f"Loaded parts from: {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load error", str(e))

    def _default_export_path(self, ext: str) -> str:
        """Suggest a default export filename.

        If the user loaded a Parts file, base the export name on that filename.
        Otherwise, fall back to a generic name.
        """
        if self._parts_source_path:
            base = os.path.splitext(os.path.basename(self._parts_source_path))[0]
            name = f"{base}_cut_plan{ext}"
            return os.path.join(os.path.dirname(self._parts_source_path), name)
        return f"cut_plan{ext}"

    def _pdf_title(self) -> str:
        """Build the PDF title shown in the top-left header.

        If a Parts file was loaded, include its filename (without extension).
        """
        if self._parts_source_path:
            stem = os.path.splitext(os.path.basename(self._parts_source_path))[0]
            return f"Cut plan — {stem}"
        return "Cut plan"

    def on_delete_stock(self) -> None:
        rows = sorted({idx.row() for idx in self.stock_view.selectionModel().selectedRows()})
        if rows:
            self.stock_model.remove_rows(rows)

    def on_delete_parts(self) -> None:
        rows = sorted({idx.row() for idx in self.parts_view.selectionModel().selectedRows()})
        if rows:
            self.parts_model.remove_rows(rows)

    def on_optimize(self) -> None:
        stock = self.stock_model.rows()
        parts = self.parts_model.rows()
        kerf = float(self.kerf_spin.value())

        if not stock or not parts:
            QtWidgets.QMessageBox.warning(self, "Missing input", "Please provide stock and parts.")
            return

        try:
            result = optimize_cut_order(stock=stock, parts=parts, kerf_mm=kerf)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Optimize error", str(e))
            return

        self._last_result = result
        self.btn_export.setEnabled(True)
        self.btn_export_pdf.setEnabled(True)
        self.render_result(result, kerf)

    def render_result(self, result: OptimizeResult, kerf_mm: float) -> None:
        kerf_u = int(round(float(kerf_mm) * SCALE))

        self.plan_view.setRowCount(0)
        for i, plan in enumerate(result.plans, start=1):
            used_u = plan.used_u(kerf_u)
            left_u = plan.leftover_u(kerf_u)
            util = (used_u / plan.stock_length_u * 100.0) if plan.stock_length_u else 0.0

            def fmt_part(p):
                mm = u_to_mm_str(p.length_u)
                return f"{mm} {p.label}".strip()

            cuts_str = "; ".join(fmt_part(p) for p in plan.parts)

            row = self.plan_view.rowCount()
            self.plan_view.insertRow(row)
            self.plan_view.setItem(row, 0, QtWidgets.QTableWidgetItem(str(i)))
            self.plan_view.setItem(row, 1, QtWidgets.QTableWidgetItem(u_to_mm_str(plan.stock_length_u)))
            self.plan_view.setItem(row, 2, QtWidgets.QTableWidgetItem(cuts_str))
            self.plan_view.setItem(row, 3, QtWidgets.QTableWidgetItem(u_to_mm_str(used_u)))
            self.plan_view.setItem(row, 4, QtWidgets.QTableWidgetItem(u_to_mm_str(left_u)))
            self.plan_view.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{util:.2f}"))

        self.plan_view.resizeColumnsToContents()

        self.status_box.clear()
        self.log("Summary:")
        for k, v in result.summary.items():
            self.log(f"  {k}: {v}")

        if result.unallocated_parts:
            self.log("")
            self.log("UNALLOCATED parts:")
            for p in result.unallocated_parts:
                self.log(f"  - {u_to_mm_str(p.length_u)} {p.label}".strip())

    def on_export(self) -> None:
        if not self._last_result:
            return
        kerf = float(self.kerf_spin.value())
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Plan CSV", self._default_export_path(".csv"), "CSV (*.csv)"
        )
        if not path:
            return
        try:
            export_plan_csv(path, self._last_result, kerf)
            QtWidgets.QMessageBox.information(
                self,
                "Exported",
                f"Exported:\n{path}\n\nAlso wrote:\n{path}.summary.csv\n{path}.unallocated.csv (may be empty)",
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export error", str(e))

    def on_export_pdf(self) -> None:
        if not self._last_result:
            return
        kerf = float(self.kerf_spin.value())
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Plan PDF", self._default_export_path(".pdf"), "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            export_plan_pdf(path, self._last_result, kerf, title=self._pdf_title())
            QtWidgets.QMessageBox.information(self, "Exported", f"Exported:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export error", str(e))


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)

    icon = QtGui.QIcon(str(_icon_path()))
    app.setWindowIcon(icon)

    w = MainWindow()
    w.setWindowIcon(icon)
    w.show()
    return app.exec()
