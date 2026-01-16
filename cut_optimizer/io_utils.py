from __future__ import annotations

from typing import List
import pandas as pd

from .optimizer import StockItem, PartItem, OptimizeResult, u_to_mm_str, SCALE, round_up_to_half_mm


def _parse_mm(value, field: str) -> float:
    """Parse a numeric mm value from CSV/XLSX and round up to 0.5mm."""
    if pd.isna(value):
        return 0.0
    try:
        mm = float(str(value).strip())
    except Exception as e:
        raise ValueError(f"Invalid {field} value: {value!r}") from e
    return round_up_to_half_mm(mm)


def load_stock_table(path: str) -> List[StockItem]:
    df = _read_table(path)
    df = _normalize_columns(df)
    if "stock_length" not in df.columns or "qty" not in df.columns:
        raise ValueError("Stock file must have columns: stock_length, qty")
    items: List[StockItem] = []
    for _, row in df.iterrows():
        items.append(StockItem(length_mm=_parse_mm(row["stock_length"], "stock_length"), qty=int(row["qty"])))
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
        items.append(
            PartItem(length_mm=_parse_mm(row["part_length"], "part_length"), qty=int(row["qty"]), label=label)
        )
    return items


def export_plan_csv(path: str, result: OptimizeResult, kerf_mm: float) -> None:
    kerf_u = int(round(float(kerf_mm) * SCALE))

    rows = []
    for i, plan in enumerate(result.plans, start=1):
        used_u = plan.used_u(kerf_u)
        left_u = plan.leftover_u(kerf_u)
        util = (used_u / plan.stock_length_u * 100.0) if plan.stock_length_u else 0.0

        def fmt_part(p):
            mm = u_to_mm_str(p.length_u)
            return f"{mm} {p.label}".strip()

        rows.append(
            {
                "stick_no": i,
                "stock_length_mm": u_to_mm_str(plan.stock_length_u),
                "cuts": "; ".join(fmt_part(p) for p in plan.parts),
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


def export_plan_pdf(path: str, result: OptimizeResult, kerf_mm: float) -> None:
    """Export a multi-page PDF cut plan.

    Layout:
      - cuts listed vertically (rows)
      - sticks listed horizontally (columns)
      - if there are too many sticks to fit, they are wrapped into multiple
        column-blocks which continue *below* the previous block (and onto new
        pages as needed).
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    except Exception as e:
        raise RuntimeError(
            "PDF export requires the 'reportlab' package. Install it with: pip install reportlab"
        ) from e

    kerf_u = int(round(float(kerf_mm) * SCALE))

    page_w, page_h = landscape(A4)
    margin = 12 * mm
    doc = SimpleDocTemplate(
        path,
        pagesize=(page_w, page_h),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title="Cut Plan",
    )

    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("Cut Plan", styles["Title"]))
    story.append(Paragraph(f"Kerf: {kerf_mm:.1f} mm", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    if not result.plans:
        story.append(Paragraph("No plan generated.", styles["Normal"]))
        doc.build(story)
        return

    # Column sizing
    cut_col_w = 14 * mm
    stick_col_w = 24 * mm
    avail_w = page_w - (margin * 2) - cut_col_w
    max_cols = max(1, int(avail_w // stick_col_w))

    def fmt_part(p) -> str:
        mm_s = u_to_mm_str(p.length_u)
        return f"{mm_s} {p.label}".strip()

    plans = result.plans
    for start in range(0, len(plans), max_cols):
        block = plans[start : start + max_cols]
        idxs = list(range(start + 1, start + 1 + len(block)))

        max_cuts = max((len(p.parts) for p in block), default=0)
        data = []

        header = ["Cut #"] + [f"Stick {i} ({u_to_mm_str(p.stock_length_u)})" for i, p in zip(idxs, block)]
        data.append(header)

        for r in range(max_cuts):
            row = [str(r + 1)]
            for p in block:
                row.append(fmt_part(p.parts[r]) if r < len(p.parts) else "")
            data.append(row)

        # Add a leftover row at the end of each block.
        leftover_row = ["Leftover"] + [u_to_mm_str(p.leftover_u(kerf_u)) for p in block]
        data.append(leftover_row)

        t = Table(
            data,
            colWidths=[cut_col_w] + [stick_col_w] * len(block),
            repeatRows=1,
            hAlign="LEFT",
        )
        t.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (1, 1), (-1, -2), "LEFT"),
                    ("ALIGN", (1, -1), (-1, -1), "CENTER"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        story.append(t)
        story.append(Spacer(1, 6 * mm))

    if result.unallocated_parts:
        story.append(PageBreak())
        story.append(Paragraph("Unallocated parts", styles["Heading2"]))
        ua = [["Length (mm)", "Label"]]
        for p in result.unallocated_parts:
            ua.append([u_to_mm_str(p.length_u), p.label])
        t2 = Table(ua, colWidths=[30 * mm, 120 * mm], repeatRows=1)
        t2.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(Spacer(1, 4 * mm))
        story.append(t2)

    doc.build(story)


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
