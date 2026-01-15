from __future__ import annotations

from typing import List
import pandas as pd

from .optimizer import StockItem, PartItem, OptimizeResult, u_to_mm_str, SCALE


def load_stock_table(path: str) -> List[StockItem]:
    df = _read_table(path)
    df = _normalize_columns(df)
    if "stock_length" not in df.columns or "qty" not in df.columns:
        raise ValueError("Stock file must have columns: stock_length, qty")
    items: List[StockItem] = []
    for _, row in df.iterrows():
        items.append(StockItem(length_mm=int(row["stock_length"]), qty=int(row["qty"])))
    return items


def load_parts_table(path: str) -> List[PartItem]:
    df = _read_table(path)
    df = _normalize_columns(df)
    if "part_length" not in df.columns or "qty" not in df.columns:
        raise ValueError("Parts file must have columns: part_length, qty (optional: label)")
    if "label" not in df.columns:
        df["label"] = ""
    items: List[PartItem] = []
    for _, row in df.iterrows():
        label = "" if pd.isna(row["label"]) else str(row["label"])
        items.append(PartItem(length_mm=int(row["part_length"]), qty=int(row["qty"]), label=label))
    return items


def export_plan_csv(path: str, result: OptimizeResult, kerf_mm: float) -> None:
    kerf_u = int(round(float(kerf_mm) * SCALE))

    rows = []
    for i, plan in enumerate(result.plans, start=1):
        used_u = plan.used_u(kerf_u)
        left_u = plan.leftover_u(kerf_u)
        kerf_cuts = max(0, len(plan.parts) - 1)
        util = (used_u / plan.stock_length_u * 100.0) if plan.stock_length_u else 0.0

        def fmt_part(p):
            mm = u_to_mm_str(p.length_u)
            return f"{mm} {p.label}".strip()

        rows.append(
            {
                "stick_no": i,
                "stock_length_mm": u_to_mm_str(plan.stock_length_u),
                "cuts": "; ".join(fmt_part(p) for p in plan.parts),
                "cut_count": len(plan.parts),
                "kerf_mm": u_to_mm_str(kerf_u),
                "kerf_cuts": kerf_cuts,
                "used_mm": u_to_mm_str(used_u),
                "leftover_mm": u_to_mm_str(left_u),
                "utilization_pct": round(util, 2),
            }
        )

    pd.DataFrame(rows).to_csv(path, index=False)
    pd.DataFrame([result.summary]).to_csv(path + ".summary.csv", index=False)

    if result.unallocated_parts:
        pd.DataFrame(
            [{"part_length_mm": u_to_mm_str(p.length_u), "label": p.label} for p in result.unallocated_parts]
        ).to_csv(path + ".unallocated.csv", index=False)


def _read_table(path: str) -> pd.DataFrame:
    p = path.lower()
    if p.endswith(".csv"):
        return pd.read_csv(path)
    if p.endswith(".xlsx") or p.endswith(".xls"):
        return pd.read_excel(path)
    raise ValueError("Unsupported file type. Use .csv or .xlsx")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df
