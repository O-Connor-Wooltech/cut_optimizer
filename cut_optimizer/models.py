from __future__ import annotations

from typing import Any, List, Optional
from PySide6 import QtCore

from .optimizer import StockItem, PartItem, round_up_to_half_mm


def _fmt_mm(mm: float) -> str:
    # Display mm values without trailing .0
    if abs(mm - round(mm)) < 1e-9:
        return str(int(round(mm)))
    return f"{mm:.1f}".rstrip("0").rstrip(".")


class StockTableModel(QtCore.QAbstractTableModel):
    HEADERS = ["stock_length (mm) (rounded up to 0.5mm)", "qty"]

    def __init__(self, rows: Optional[List[StockItem]] = None) -> None:
        super().__init__()
        self._rows: List[StockItem] = rows or []

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 2

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole) -> Any:
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            return _fmt_mm(row.length_mm) if index.column() == 0 else row.qty
        return None

    def setData(self, index: QtCore.QModelIndex, value: Any, role: int = QtCore.Qt.EditRole) -> bool:
        if role != QtCore.Qt.EditRole or not index.isValid():
            return False
        r, c = index.row(), index.column()
        row = self._rows[r]
        if c == 0:
            try:
                fv = float(str(value).strip())
            except Exception:
                return False
            self._rows[r] = StockItem(length_mm=round_up_to_half_mm(fv), qty=row.qty)
        elif c == 1:
            try:
                iv = int(str(value).strip())
            except Exception:
                return False
            self._rows[r] = StockItem(length_mm=row.length_mm, qty=max(0, iv))
        else:
            return False
        self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])
        return True

    def set_rows(self, rows: List[StockItem]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self) -> List[StockItem]:
        return list(self._rows)

    def add_row(self) -> None:
        self.beginInsertRows(QtCore.QModelIndex(), len(self._rows), len(self._rows))
        self._rows.append(StockItem(length_mm=0, qty=0))
        self.endInsertRows()

    def remove_rows(self, row_indices: List[int]) -> None:
        for r in sorted(set(row_indices), reverse=True):
            if 0 <= r < len(self._rows):
                self.beginRemoveRows(QtCore.QModelIndex(), r, r)
                self._rows.pop(r)
                self.endRemoveRows()


class PartsTableModel(QtCore.QAbstractTableModel):
    HEADERS = ["part_length (mm) (rounded up to 0.5mm)", "qty", "label (optional)"]

    def __init__(self, rows: Optional[List[PartItem]] = None) -> None:
        super().__init__()
        self._rows: List[PartItem] = rows or []

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 3

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole) -> Any:
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            if index.column() == 0:
                return _fmt_mm(row.length_mm)
            if index.column() == 1:
                return row.qty
            if index.column() == 2:
                return row.label
        return None

    def setData(self, index: QtCore.QModelIndex, value: Any, role: int = QtCore.Qt.EditRole) -> bool:
        if role != QtCore.Qt.EditRole or not index.isValid():
            return False
        r, c = index.row(), index.column()
        row = self._rows[r]
        if c in (0, 1):
            if c == 0:
                try:
                    fv = float(str(value).strip())
                except Exception:
                    return False
                self._rows[r] = PartItem(length_mm=round_up_to_half_mm(fv), qty=row.qty, label=row.label)
            else:
                try:
                    iv = int(str(value).strip())
                except Exception:
                    return False
                self._rows[r] = PartItem(length_mm=row.length_mm, qty=max(0, iv), label=row.label)
        elif c == 2:
            self._rows[r] = PartItem(length_mm=row.length_mm, qty=row.qty, label=str(value))
        else:
            return False
        self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])
        return True

    def set_rows(self, rows: List[PartItem]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self) -> List[PartItem]:
        return list(self._rows)

    def add_row(self) -> None:
        self.beginInsertRows(QtCore.QModelIndex(), len(self._rows), len(self._rows))
        self._rows.append(PartItem(length_mm=0, qty=0, label=""))
        self.endInsertRows()

    def remove_rows(self, row_indices: List[int]) -> None:
        for r in sorted(set(row_indices), reverse=True):
            if 0 <= r < len(self._rows):
                self.beginRemoveRows(QtCore.QModelIndex(), r, r)
                self._rows.pop(r)
                self.endRemoveRows()
